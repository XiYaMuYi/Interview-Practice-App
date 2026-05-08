"""LLM Gateway — unified entry for all model calls."""

from typing import AsyncGenerator

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.infra.llm.prompt_registry import prompt_registry

logger = get_logger(__name__)


class LLMProviderError(AppException):
    def __init__(self, provider: str, detail: str):
        super().__init__(
            status_code=502,
            detail=f"LLM provider '{provider}' error: {detail}",
            code="LLM_PROVIDER_ERROR",
        )


class LLMGateway:
    """All LLM calls must go through this gateway.

    Routes to the configured provider (currently only DashScope).
    """

    def __init__(self) -> None:
        self.provider_name = settings.LLM_PROVIDER
        self.model_name = settings.LLM_MODEL_NAME
        self._provider = self._init_provider()

    def _init_provider(self):
        if self.provider_name == "dashscope":
            from app.infra.llm.providers.dashscope import DashScopeProvider

            return DashScopeProvider()
        raise LLMProviderError(self.provider_name, f"Unknown provider '{self.provider_name}'")

    # ── Chat completions ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: str | None = None,
    ) -> str:
        """Send a chat-completion request and return the assistant content."""
        logger.info(f"LLM chat: model={model or self.model_name}, messages={len(messages)}, temp={temperature}")
        try:
            return await self._provider.chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except Exception as e:
            raise LLMProviderError(self.provider_name, str(e))

    async def chat_json(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict:
        """Send a chat-completion request expecting JSON output."""
        logger.info(f"LLM chat (json): model={model or self.model_name}, messages={len(messages)}")
        try:
            return await self._provider.chat_completion_json(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except Exception as e:
            raise LLMProviderError(self.provider_name, str(e))

    # ── Streaming ───────────────────────────────────────────────────

    async def stream_chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks from a streaming chat response."""
        logger.info(f"LLM stream: model={model or self.model_name}, messages={len(messages)}")
        try:
            async for chunk in self._provider.stream_chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            ):
                if chunk.get("delta"):
                    yield chunk["delta"]
        except Exception as e:
            raise LLMProviderError(self.provider_name, str(e))

    # ── Embeddings ──────────────────────────────────────────────────

    async def embed(self, texts: list[str], *, model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        logger.info(f"LLM embed: texts={len(texts)}")
        try:
            return await self._provider.embedding(texts, model=model or settings.EMBEDDING_MODEL_PATH, dimensions=dimensions)
        except Exception as e:
            raise LLMProviderError(self.provider_name, str(e))

    # ── Prompt-based helpers ────────────────────────────────────────

    async def chat_with_prompt(
        self,
        prompt_key: str,
        *,
        variables: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Build messages from a registered prompt template and send."""
        system_template = prompt_registry.get_system(prompt_key)
        if system_template is None:
            raise LLMProviderError(self.provider_name, f"Prompt '{prompt_key}' not found in registry")

        system_content = system_template
        if variables:
            for key, value in variables.items():
                system_content = system_content.replace(f"{{{{{key}}}}}", value)

        messages = [{"role": "system", "content": system_content}]
        return await self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    async def chat_json_with_prompt(
        self,
        prompt_key: str,
        *,
        variables: dict[str, str] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """Build messages from a registered prompt template and send with JSON format."""
        system_template = prompt_registry.get_system(prompt_key)
        if system_template is None:
            raise LLMProviderError(self.provider_name, f"Prompt '{prompt_key}' not found in registry")

        system_content = system_template
        if variables:
            for key, value in variables.items():
                system_content = system_content.replace(f"{{{{{key}}}}}", value)

        messages = [{"role": "system", "content": system_content}]
        return await self.chat_json(messages, temperature=temperature, max_tokens=max_tokens)


# ── Singleton ──────────────────────────────────────────────────────

llm_gateway = LLMGateway()
