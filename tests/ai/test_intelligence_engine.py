"""Unit tests for the structured AI orchestration boundary."""

from __future__ import annotations

import asyncio
import json

from ai.engine import AIEngine
from ai.llm import GenerationRequest, GenerationResponse
from ai.model_manager import ModelManager
from ai.response_parser import ResponseParser


class FakeModelClient:
    model_name = "fake-local"

    def __init__(self, content: str, available: bool = True) -> None:
        self.content = content
        self.available = available
        self.request: GenerationRequest | None = None

    async def is_available(self) -> bool:
        return self.available

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.request = request
        return GenerationResponse(self.content, self.model_name, 100, 50)

    async def close(self) -> None:
        return None


def model_payload() -> dict:
    return {
        "executive_summary": "Performance is improving.",
        "channel_health": {"status": "healthy"},
        "key_findings": [{"finding": "CTR improved", "evidence": ["graph:ctr"]}],
        "growth_opportunities": [],
        "threats": [],
        "predictions": [],
        "action_plan": [
            {"title": "Later", "priority": "low"},
            {"title": "First", "priority": "high"},
        ],
        "video_ideas": [],
        "thumbnail_ideas": [],
        "seo_suggestions": [],
        "confidence_scores": {"overall": 0.9},
    }


def complete_knowledge() -> dict:
    return {
        "analytics": {"summary": {"views": 100}},
        "graph_intelligence": {"graphs": [{"type": "views", "trend": "increasing"}]},
        "competitor_intelligence": {"benchmarks": []},
        "news_intelligence": {"topics": []},
    }


def test_engine_accepts_only_supplied_context_and_returns_stable_contract() -> None:
    client = FakeModelClient(json.dumps(model_payload()))
    engine = AIEngine(ModelManager([client]))

    result = asyncio.run(engine.analyze(complete_knowledge()))

    assert result["executive_summary"] == "Performance is improving."
    assert result["action_plan"][0]["title"] == "First"
    assert result["raw_ai_response"]
    assert result["timestamp"]
    assert client.request is not None
    assert '"views":100' in client.request.user_prompt


def test_engine_degrades_when_no_local_model_is_available() -> None:
    engine = AIEngine(ModelManager([FakeModelClient("", available=False)]))

    result = asyncio.run(engine.analyze({"analytics": {}}))

    assert result["degraded"] is True
    assert result["warnings"]


def test_parser_recovers_fenced_json() -> None:
    parser = ResponseParser()

    result = parser.parse("Result:\n```json\n" + json.dumps(model_payload()) + "\n```")

    assert result.executive_summary == "Performance is improving."
    assert result.warnings


def test_parser_gracefully_preserves_unparseable_response() -> None:
    result = ResponseParser().parse("plain text response")

    assert result.degraded is True
    assert result.raw_ai_response == "plain text response"
