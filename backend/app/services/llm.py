"""LLM abstraction. One OpenAI-compatible client covers OpenAI *and* Ollama (/v1 endpoint)."""

import logging
from typing import Protocol

from openai import OpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    available: bool

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


class NullLLM:
    """Used when LLM_PROVIDER=rules. Agents fall back to deterministic logic."""

    available = False

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        raise RuntimeError("LLM is disabled (LLM_PROVIDER=rules)")


class OpenAICompatibleLLM:
    available = True

    def __init__(self, *, api_key: str, base_url: str | None, model: str, timeout: float) -> None:
        self._client = OpenAI(api_key=api_key or "ollama", base_url=base_url, timeout=timeout)
        self._model = model

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **kwargs,
        )
        return response.choices[0].message.content or ""


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAICompatibleLLM(
            api_key=settings.openai_api_key,
            base_url=None,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "ollama":
        return OpenAICompatibleLLM(
            api_key="ollama",
            base_url=settings.ollama_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    return NullLLM()
