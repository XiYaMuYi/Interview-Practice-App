"""DashScope LLM provider。

这是当前项目使用的具体模型提供方实现，负责把统一的 LLM 请求
转换成 DashScope 的 HTTP 调用。

注意：这个文件只负责"怎么调用 API"，不负责业务 prompt，也不负责
工作流编排。
"""

import asyncio
import json

import httpx

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


class DashScopeError(AppException):
    """DashScope 调用异常。

    用统一的业务异常包装底层 HTTP/解析错误，避免上层处理 provider
    原生异常。
    """

    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=f"DashScope error: {detail}", code="LLM_PROVIDER_ERROR")


class DashScopeProvider:
    """DashScope provider 的具体实现。

    这个类负责：
    - 组装请求参数
    - 发起 HTTP 请求
    - 处理重试（指数退避）
    - 解析返回值
    - 提供流式输出和 embedding 能力
    """

    def __init__(self) -> None:
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.embedding_api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
        self.model = settings.LLM_MODEL_NAME
        self.max_retries = settings.LLM_MAX_RETRIES
        self.timeout = settings.LLM_TIMEOUT

        if not self.api_key:
            raise DashScopeError("LLM_API_KEY is not configured")

    # ── 普通对话调用 ───────────────────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        """发送普通对话请求，并返回模型输出文本。

        这个函数是 provider 层最常用的基础能力。
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = httpx.Timeout(self.timeout, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                choices = data.get("choices", [])
                if not choices:
                    raise DashScopeError(f"Empty choices from LLM: {data}")

                content = choices[0]["message"]["content"]
                logger.debug(f"LLM response (attempt {attempt}): {len(content)} chars")
                return content

            except httpx.TimeoutException as e:
                last_err = e
                logger.warning(f"DashScope timeout (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))
            except httpx.HTTPStatusError as e:
                last_err = e
                logger.warning(f"DashScope HTTP error (attempt {attempt}): {e.response.status_code}")
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))
                elif e.response.status_code >= 500:
                    pass  # will retry on next iteration
                else:
                    raise DashScopeError(f"HTTP {e.response.status_code}: {e.response.text}")
            except (httpx.RequestError, KeyError, IndexError) as e:
                last_err = e
                logger.warning(f"DashScope request error (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))

        raise DashScopeError(f"All {self.max_retries} attempts failed: {last_err}")

    # ── 流式对话调用 ──────────────────────────────────────────────

    async def stream_chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ):
        """以流式方式返回模型生成的文本片段。

        主要用于前端边生成边显示的交互体验。
        包含重试 + 超时降级逻辑。
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = httpx.Timeout(self.timeout, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[len("data:"):].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    finish = choices[0].get("finish_reason")
                                    if content or finish:
                                        yield {"delta": content, "finish_reason": finish}
                            except json.JSONDecodeError:
                                continue
                return  # success

            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                last_err = e
                logger.warning(f"DashScope stream error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    raise DashScopeError(f"Stream failed after {self.max_retries} attempts: {last_err}")

    # ── JSON 结构化输出 ─────────────────────────────────────────

    async def chat_completion_json(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict:
        """发送期望 JSON 输出的对话请求。

        这个方法会在 provider 侧要求结构化输出，并在这里做基础 JSON
        清洗与校验。
        """
        content = await self.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            response_format={"type": "json_object"},
        )
        # Strip markdown code fences if the model wraps the JSON in ```json ... ```
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise DashScopeError(f"LLM returned invalid JSON: {e}\nContent: {content[:200]}")

    # ── 向量化 / Embeddings ───────────────────────────────────────

    async def embedding(
        self,
        texts: list[str],
        *,
        model: str = "text-embedding-v3",
        dimensions: int | None = None,
    ) -> list[list[float]]:
        """为一组文本生成向量表示。

        主要用于题目检索、知识检索、简历匹配等 RAG 场景。
        """
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {"texts": texts},
        }
        if dimensions:
            payload["dimensions"] = dimensions

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = httpx.Timeout(self.timeout, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    resp = await client.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                embeddings: list[list[float]] = []
                for item in sorted(data.get("data", []), key=lambda x: x["index"]):
                    embeddings.append(item["embedding"])
                return embeddings

            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                last_err = e
                logger.warning(f"DashScope embedding error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))

        raise DashScopeError(f"Embedding failed after {self.max_retries} attempts: {last_err}")
