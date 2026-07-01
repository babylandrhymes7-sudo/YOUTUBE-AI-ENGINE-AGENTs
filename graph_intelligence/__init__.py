"""Deterministic graph normalization and analysis for YouTube metrics."""

from typing import TYPE_CHECKING, Any

from .models import GraphInput, GraphPointInput

if TYPE_CHECKING:
    from .service import GraphService

__all__ = ["GraphInput", "GraphPointInput", "GraphService"]


def __getattr__(name: str) -> Any:
    """Load the SQLAlchemy-backed service only when an integration requests it."""

    if name == "GraphService":
        from .service import GraphService

        return GraphService
    raise AttributeError(name)
