"""DashScope LLM provider — OpenAI compatible API."""

import json

import httpx

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


class DashScopeError(AppException):
    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=f"DashScope error: {detail}", code="LLM_PROVIDER_ERROR")


class DashScopeProvider:
    """Calls DashScope via its OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL_NAME
        self.max_retries = settings.LLM_MAX_RETRIES
        self.timeout = settings.LLM_TIMEOUT

        if not self.api_key:
            raise DashScopeError("LLM_API_KEY is not configured")

    # ── Chat completion ──────────────────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat-completion request and return the assistant content string."""
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
                async with httpx.AsyncClient(timeout=self.timeout) as client:
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

            except httpx.HTTPStatusError as e:
                last_err = e
                logger.warning(f"DashScope HTTP error (attempt {attempt}): {e.response.status_code}")
            except (httpx.RequestError, KeyError, IndexError) as e:
                last_err = e
                logger.warning(f"DashScope request error (attempt {attempt}): {e}")

        raise DashScopeError(f"All {self.max_retries} attempts failed: {last_err}")

    # ── Streaming chat completion ────────────────────────────────────

    async def stream_chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ):
        """Yield streaming text chunks from the LLM."""
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

    # ── JSON-structured output ───────────────────────────────────────

    async def chat_completion_json(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict:
        """Send a chat-completion request expecting JSON response."""
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

    # ── Embeddings ───────────────────────────────────────────────────

    async def embedding(
        self,
        texts: list[str],
        *,
        model: str = "text-embedding-v3",
        dimensions: int | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {"texts": texts},
        }
        if dimensions:
            payload["dimensions"] = dimensions

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
