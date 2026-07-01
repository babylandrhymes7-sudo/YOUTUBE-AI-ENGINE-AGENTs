"""Async localhost-only Ollama transport."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx

from app.logging import get_logger

from .llm import GenerationRequest, GenerationResponse, GenerationTimeoutError, ModelUnavailableError

logger = get_logger(__name__)


class OllamaClient:
    """Communicate with a local Ollama server using its HTTP API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
        retries: int = 2,
        retry_delay_seconds: float = 1.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OllamaClient only permits localhost endpoints")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._retries = max(0, retries)
        self._retry_delay = max(0.0, retry_delay_seconds)
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = http_client is None

    @property
    def model_name(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(f"{self._base_url}/api/tags", timeout=min(self._timeout, 5.0))
            response.raise_for_status()
            models = response.json().get("models", [])
            return any(
                self._matches_model(item.get("name")) or self._matches_model(item.get("model"))
                for item in models
            )
        except (httpx.HTTPError, ValueError):
            return False

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        payload = {
            "model": self._model,
            "stream": False,
            "format": request.response_format,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "options": {"temperature": request.temperature},
        }
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.post(
                    f"{self._base_url}/api/chat", json=payload, timeout=self._timeout
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Ollama generation succeeded model=%s retries_used=%s prompt_tokens=%s completion_tokens=%s",
                    self._model,
                    attempt,
                    data.get("prompt_eval_count"),
                    data.get("eval_count"),
                )
                return GenerationResponse(
                    content=data.get("message", {}).get("content", ""),
                    model=data.get("model", self._model),
                    prompt_tokens=data.get("prompt_eval_count"),
                    completion_tokens=data.get("eval_count"),
                    total_duration_ns=data.get("total_duration"),
                    metadata={"done_reason": data.get("done_reason"), "retries_used": attempt},
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("Ollama generation timed out attempt=%s model=%s", attempt + 1, self._model)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                logger.warning("Ollama generation failed attempt=%s model=%s error=%s", attempt + 1, self._model, type(exc).__name__)
            if attempt < self._retries:
                await asyncio.sleep(self._retry_delay * (2**attempt))
        if isinstance(last_error, httpx.TimeoutException):
            raise GenerationTimeoutError(f"generation timed out for model {self._model}") from last_error
        raise ModelUnavailableError(f"local Ollama model unavailable: {self._model}") from last_error

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _matches_model(self, candidate: str | None) -> bool:
        if not candidate:
            return False
        return candidate == self._model or candidate.split(":", 1)[0] == self._model.split(":", 1)[0]
