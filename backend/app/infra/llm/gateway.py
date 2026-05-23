"""LLM Gateway。

这是后端所有大模型调用的统一入口。无论是讲解、追问、分类、
抽取、评分还是向量化，都应该先经过这里，再转到具体 provider。

这样做的好处是：
- 业务层不关心底层模型厂商
- 后续切换模型只需要改 provider
- 统一做日志、异常包装和调用策略控制
"""

import asyncio
import hashlib
import time
from typing import AsyncGenerator

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.infra.cache.cache_service import TTL_QUESTION, get_cache, set_cache
from app.infra.events.event_publisher import event_publisher
from app.infra.events.event_types import (
    CACHE_HIT,
    CACHE_MISS,
    LLM_CALL_FAILED,
    LLM_CALL_SUCCESS,
)
from app.infra.llm.prompt_registry import prompt_registry

logger = get_logger(__name__)


# ── Async call logging helper ──────────────────────────────────────


def _truncate(text: str, max_len: int = 500) -> str:
    """截断文本至最大长度，避免日志字段过长。"""
    if not text:
        return ""
    return text[:max_len]


async def _log_llm_call(
    *,
    task_id=None,
    session_id: str | None = None,
    prompt_key: str,
    prompt_version: str,
    model_name: str,
    request_preview: str,
    response_preview: str,
    duration_ms: int,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """异步写入 LLM 调用日志到数据库，并发布事件。

    这个函数通过独立的数据库连接写入，不依赖请求级别的 session，
    确保即使主流程已经返回，日志仍然可以写入。
    """
    try:
        from app.domain.models import LLMCallLog
        from app.infra.db.session import async_session

        log = LLMCallLog(
            task_id=task_id,
            session_id=session_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            model_name=model_name,
            request_preview=_truncate(request_preview),
            response_preview=_truncate(response_preview),
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
            error_message=error_message,
        )
        async with async_session() as session:
            session.add(log)
            await session.commit()

        # Publish LLM call event
        try:
            from app.infra.events.event_publisher import event_publisher
            from app.infra.events.event_types import LLM_CALL_FAILED, LLM_CALL_SUCCESS

            event_type = LLM_CALL_SUCCESS if status == "success" else LLM_CALL_FAILED
            await event_publisher.publish(event_type, {
                "task_id": str(task_id) if task_id else None,
                "prompt_key": prompt_key,
                "prompt_version": prompt_version,
                "model_name": model_name,
                "duration_ms": duration_ms,
                "status": status,
                "error_message": error_message,
            })
        except Exception:
            pass  # Graceful fallback
    except Exception as e:
        logger.warning(f"Failed to write LLM call log: {e}")


def _extract_messages_preview(messages: list[dict]) -> str:
    """从消息列表提取预览文本。"""
    if not messages:
        return ""
    parts = []
    for m in messages:
        content = m.get("content", "")
        if content:
            parts.append(content)
    return " ".join(parts)


class LLMProviderError(AppException):
    """统一包装模型厂商异常。

    为什么要单独定义这个异常：
    - 上层业务只关心“模型调用失败了”，不关心底层 HTTP/SDK 的细节
    - 统一返回 502，方便前端和网关识别成上游模型错误
    - 便于做错误码统一化
    """

    def __init__(self, provider: str, detail: str):
        super().__init__(
            status_code=502,
            detail=f"LLM provider '{provider}' error: {detail}",
            code="LLM_PROVIDER_ERROR",
        )


class LLMGateway:
    """所有模型调用必须经过这个网关。

    这里是后端对模型能力的“统一门面”：
    - chat：普通对话
    - chat_json：结构化 JSON 输出
    - stream_chat：流式输出
    - embed：向量化
    - chat_with_prompt：注册 Prompt 模板调用
    - chat_json_with_prompt：注册 Prompt 模板 + JSON 输出

    上层服务不应该直接碰 provider，而是统一通过这里发起调用。
    """

    def __init__(self) -> None:
        self.provider_name = settings.LLM_PROVIDER
        self.model_name = settings.LLM_MODEL_NAME
        self._provider = None

    @property
    def provider(self):
        """懒加载 provider。

        第一次真正用到模型能力时才初始化 provider，可以减少启动时的
       耦合和资源占用。
        """
        if self._provider is None:
            self._provider = self._init_provider()
        return self._provider

    def _init_provider(self):
        """根据配置初始化具体 provider。

        当前 MVP 只接了 DashScope，但这里保留工厂式写法，后续接别的
        模型提供方时不用改业务代码。
        """
        if self.provider_name == "dashscope":
            from app.infra.llm.providers.dashscope import DashScopeProvider

            return DashScopeProvider()
        raise LLMProviderError(self.provider_name, f"Unknown provider '{self.provider_name}'")

    # ── 普通对话调用 ───────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
        task_id=None,
        session_id: str | None = None,
    ) -> str:
        """发送普通对话请求，返回模型生成的文本内容。

        适用于：讲解、追问、总结、简单生成等非结构化输出场景。
        """
        logger.info(f"LLM chat: model={model or self.model_name}, messages={len(messages)}, temp={temperature}")
        start = time.monotonic()
        try:
            result = await self.provider.chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_chat",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview=result,
                    duration_ms=duration_ms,
                    status="success",
                )
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_chat",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview="",
                    duration_ms=duration_ms,
                    status="failed",
                    error_code="LLM_PROVIDER_ERROR",
                    error_message=str(e),
                )
            )
            raise LLMProviderError(self.provider_name, str(e))

    async def chat_json(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
        task_id=None,
        session_id: str | None = None,
    ) -> dict:
        """发送要求 JSON 输出的对话请求。

        适用于：分类、抽取、评分、结构化讲解、追问结果等。
        这里会强制要求 provider 返回 JSON，并在网关层做基础解析。
        """
        logger.info(f"LLM chat (json): model={model or self.model_name}, messages={len(messages)}")
        start = time.monotonic()
        try:
            result = await self.provider.chat_completion_json(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            import json

            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_chat_json",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview=json.dumps(result)[:500],
                    duration_ms=duration_ms,
                    status="success",
                )
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_chat_json",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview="",
                    duration_ms=duration_ms,
                    status="failed",
                    error_code="LLM_PROVIDER_ERROR",
                    error_message=str(e),
                )
            )
            raise LLMProviderError(self.provider_name, str(e))

    # ── 流式输出 ───────────────────────────────────────────────────

    async def stream_chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
        task_id=None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """以流式方式输出文本片段。

        适用于前端 SSE、打字机效果、流式面试追问等场景。
        """
        logger.info(f"LLM stream: model={model or self.model_name}, messages={len(messages)}")
        start = time.monotonic()
        collected = []
        try:
            async for chunk in self.provider.stream_chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            ):
                if chunk.get("delta"):
                    collected.append(chunk["delta"])
                    yield chunk["delta"]
            duration_ms = int((time.monotonic() - start) * 1000)
            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_stream",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview="".join(collected)[:500],
                    duration_ms=duration_ms,
                    status="success",
                )
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            asyncio.create_task(
                _log_llm_call(
                    task_id=task_id,
                    session_id=session_id,
                    prompt_key=prompt_key or "direct_stream",
                    prompt_version=prompt_version or "unknown",
                    model_name=model or self.model_name,
                    request_preview=_extract_messages_preview(messages),
                    response_preview="".join(collected)[:500],
                    duration_ms=duration_ms,
                    status="failed",
                    error_code="LLM_PROVIDER_ERROR",
                    error_message=str(e),
                )
            )
            raise LLMProviderError(self.provider_name, str(e))

    # ── 向量化 / Embeddings ───────────────────────────────────────

    async def embed(self, texts: list[str], *, model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
        """对一组文本生成向量表示。

        适用于题目入库、知识节点入库、简历经历检索等场景。
        """
        logger.info(f"LLM embed: texts={len(texts)}")
        try:
            return await self.provider.embedding(texts, model=model or settings.EMBEDDING_MODEL_PATH, dimensions=dimensions)
        except Exception as e:
            raise LLMProviderError(self.provider_name, str(e))

    # ── 基于 Prompt Registry 的封装调用 ─────────────────────────

    async def chat_with_prompt(
        self,
        prompt_key: str,
        *,
        variables: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        task_id=None,
        session_id: str | None = None,
    ) -> str:
        """从注册的 Prompt 模板构建消息并发送。

        好处是：
        - prompt 有统一版本管理
        - 业务代码只传变量，不直接拼长提示词
        - 更容易做 prompt 回溯和 A/B 调优
        """
        template = prompt_registry.get_template(prompt_key)
        if template is None:
            raise LLMProviderError(self.provider_name, f"Prompt '{prompt_key}' not found in registry")

        system_content = template.system_template
        if variables:
            for key, value in variables.items():
                system_content = system_content.replace(f"{{{{{key}}}}}", value)

        messages = [{"role": "system", "content": system_content}]
        return await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_key=prompt_key,
            prompt_version=template.version,
            task_id=task_id,
            session_id=session_id,
        )

    async def chat_json_with_prompt(
        self,
        prompt_key: str,
        *,
        variables: dict[str, str] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        task_id=None,
        session_id: str | None = None,
    ) -> dict:
        """从注册的 Prompt 模板构建消息，并要求返回 JSON。

        适用于结构化结果类任务，比如分类、评分、抽取、聚合等。
        """
        template = prompt_registry.get_template(prompt_key)
        if template is None:
            raise LLMProviderError(self.provider_name, f"Prompt '{prompt_key}' not found in registry")

        system_content = template.system_template
        if variables:
            for key, value in variables.items():
                system_content = system_content.replace(f"{{{{{key}}}}}", value)

        # Build cache key from prompt_key + variables hash + version
        if variables:
            var_hash = hashlib.sha256(
                "|".join(f"{k}={v}" for k, v in sorted(variables.items())).encode()
            ).hexdigest()[:16]
        else:
            var_hash = "no_vars"
        cache_key = f"app:llm:json:{prompt_key}:{template.version}:{var_hash}"

        # Check cache for LLM response
        cached = await get_cache(cache_key)
        if cached is not None:
            logger.info(f"LLM cache HIT: {cache_key}")
            try:
                await event_publisher.publish(CACHE_HIT, {
                    "task_id": str(task_id) if task_id else None,
                    "cache_key": cache_key,
                })
            except Exception:
                pass
            return cached

        try:
            await event_publisher.publish(CACHE_MISS, {
                "task_id": str(task_id) if task_id else None,
                "cache_key": cache_key,
            })
        except Exception:
            pass

        messages = [{"role": "system", "content": system_content}]
        result = await self.chat_json(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_key=prompt_key,
            prompt_version=template.version,
            task_id=task_id,
            session_id=session_id,
        )

        # Cache the LLM response (TTL based on question TTL = 30min)
        try:
            await set_cache(cache_key, result, ttl=TTL_QUESTION)
        except Exception:
            pass

        return result

    async def stream_chat_with_prompt(
        self,
        prompt_key: str,
        *,
        variables: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        task_id=None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """从 Prompt 模板构建消息并以流式方式输出。

        每个 chunk 直接 yield，支持 token 级流式。
        适用于需要逐字输出的非结构化文本场景。
        """
        template = prompt_registry.get_template(prompt_key)
        if template is None:
            raise LLMProviderError(self.provider_name, f"Prompt '{prompt_key}' not found in registry")

        system_content = template.system_template
        if variables:
            for key, value in variables.items():
                system_content = system_content.replace(f"{{{{{key}}}}}", value)

        messages = [{"role": "system", "content": system_content}]
        async for chunk in self.stream_chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_key=prompt_key,
            prompt_version=template.version,
            task_id=task_id,
            session_id=session_id,
        ):
            yield chunk


# ── Singleton ──────────────────────────────────────────────────────

llm_gateway = LLMGateway()
