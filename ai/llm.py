"""Provider-independent local language-model interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class AIEngineError(RuntimeError):
    """Base error for local AI generation failures."""


class ModelUnavailableError(AIEngineError):
    """Raised when the configured local model cannot be reached."""


class GenerationTimeoutError(AIEngineError):
    """Raised when local generation exceeds its timeout."""


@dataclass(frozen=True)
class GenerationRequest:
    """One model generation request."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    response_format: str = "json"


@dataclass(frozen=True)
class GenerationResponse:
    """Provider-neutral model response and optional telemetry."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_duration_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalModelClient(Protocol):
    """Interface implemented by Ollama and future localhost model runtimes."""

    @property
    def model_name(self) -> str: ...

    async def is_available(self) -> bool: ...

    async def generate(self, request: GenerationRequest) -> GenerationResponse: ...

    async def close(self) -> None: ...
