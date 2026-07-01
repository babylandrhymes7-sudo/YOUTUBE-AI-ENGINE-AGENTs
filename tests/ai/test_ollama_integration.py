"""Opt-in integration test against the real localhost Ollama instance."""

from __future__ import annotations

import asyncio
import os

import pytest

from ai.qwen import create_qwen_engine


@pytest.mark.skipif(os.getenv("RUN_OLLAMA_INTEGRATION") != "1", reason="requires local Ollama and Qwen")
def test_local_qwen_returns_structured_intelligence() -> None:
    async def run() -> dict:
        engine = create_qwen_engine()
        try:
            return await engine.analyze(
                {
                    "analytics": {"summary": {"views": 100, "note": "pre-calculated"}},
                    "graph_intelligence": {"views": {"trend": "increasing"}},
                }
            )
        finally:
            await engine.close()

    result = asyncio.run(run())
    assert "executive_summary" in result
    assert "action_plan" in result
