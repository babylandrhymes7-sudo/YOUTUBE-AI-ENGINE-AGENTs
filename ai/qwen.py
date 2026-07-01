"""Composition root for the locally hosted Qwen intelligence engine."""

from app.config import settings

from .engine import AIEngine, AIEngineConfig
from .model_manager import ModelManager
from .ollama import OllamaClient


def create_qwen_engine() -> AIEngine:
    """Create the default localhost-only Qwen engine."""

    client = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        retries=settings.ollama_retry_attempts,
        retry_delay_seconds=settings.ollama_retry_delay_seconds,
    )
    return AIEngine(
        ModelManager([client]),
        config=AIEngineConfig(preferred_model=settings.ollama_model),
    )
