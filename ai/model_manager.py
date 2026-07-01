"""Local model selection independent of AI business logic."""

from __future__ import annotations

from .llm import LocalModelClient, ModelUnavailableError


class ModelManager:
    """Choose the first available injected local model client."""

    def __init__(self, clients: list[LocalModelClient]) -> None:
        if not clients:
            raise ValueError("at least one local model client is required")
        self._clients = clients

    async def select(self, preferred_model: str | None = None) -> LocalModelClient:
        ordered = sorted(self._clients, key=lambda client: client.model_name != preferred_model)
        for client in ordered:
            if await client.is_available():
                return client
        raise ModelUnavailableError("no configured local model is available")

    async def close(self) -> None:
        for client in self._clients:
            await client.close()
