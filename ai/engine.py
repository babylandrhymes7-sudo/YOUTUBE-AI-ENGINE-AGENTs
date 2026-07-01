"""Central orchestration for structured local AI intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.logging import get_logger

from .confidence import ConfidenceScorer
from .context_builder import ContextBuilder
from .contracts import IntelligenceResult, KnowledgeContext
from .llm import AIEngineError, GenerationRequest
from .model_manager import ModelManager
from .prompt_manager import PromptManager
from .recommendation_engine import RecommendationEngine
from .response_parser import ResponseParser

logger = get_logger(__name__)


@dataclass(frozen=True)
class AIEngineConfig:
    prompt_name: str = "intelligence"
    prompt_version: str = "v1"
    preferred_model: str | None = None
    temperature: float = 0.2


class AIEngine:
    """Transform supplied structured knowledge into strategic intelligence."""

    def __init__(
        self,
        model_manager: ModelManager,
        *,
        prompt_manager: PromptManager | None = None,
        context_builder: ContextBuilder | None = None,
        response_parser: ResponseParser | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        config: AIEngineConfig | None = None,
    ) -> None:
        self._models = model_manager
        self._prompts = prompt_manager or PromptManager()
        self._context = context_builder or ContextBuilder()
        self._parser = response_parser or ResponseParser()
        self._recommendations = recommendation_engine or RecommendationEngine()
        self._confidence = confidence_scorer or ConfidenceScorer()
        self._config = config or AIEngineConfig()

    async def analyze(self, knowledge: KnowledgeContext | dict[str, Any]) -> dict[str, Any]:
        """Generate intelligence without collecting, querying, or calculating source metrics."""

        try:
            context = knowledge if isinstance(knowledge, KnowledgeContext) else KnowledgeContext.from_dict(knowledge)
        except (TypeError, ValueError):
            logger.exception("AI knowledge context validation failed")
            raise
        try:
            bundle = self._prompts.load(self._config.prompt_name, self._config.prompt_version)
            context_json = self._context.build(context)
        except (OSError, TypeError, ValueError) as exc:
            logger.exception(
                "AI request preparation failed prompt_version=%s error=%s",
                self._config.prompt_version,
                type(exc).__name__,
            )
            return self._degraded(context, f"AI request preparation failed: {type(exc).__name__}").to_dict()
        request = GenerationRequest(
            system_prompt=bundle.system,
            user_prompt=self._prompts.render_user(bundle, context_json),
            temperature=self._config.temperature,
        )
        started = perf_counter()
        try:
            client = await self._models.select(self._config.preferred_model)
            response = await client.generate(request)
        except AIEngineError as exc:
            logger.error(
                "AI generation unavailable prompt_version=%s error=%s",
                bundle.version,
                type(exc).__name__,
            )
            return self._degraded(context, str(exc)).to_dict()
        generation_ms = (perf_counter() - started) * 1000.0

        parsing_started = perf_counter()
        result = self._parser.parse(response.content)
        parsing_ms = (perf_counter() - parsing_started) * 1000.0
        result = self._recommendations.prioritize(result)
        result = self._confidence.score(result, context)
        for warning in result.warnings:
            logger.warning(
                "AI response warning model=%s prompt_version=%s warning=%s",
                response.model,
                bundle.version,
                warning,
            )

        logger.info(
            "AI generation complete model=%s prompt_version=%s generation_ms=%.2f parsing_ms=%.2f "
            "prompt_tokens=%s completion_tokens=%s",
            response.model,
            bundle.version,
            generation_ms,
            parsing_ms,
            response.prompt_tokens,
            response.completion_tokens,
        )
        return result.to_dict()

    async def close(self) -> None:
        await self._models.close()

    def _degraded(self, context: KnowledgeContext, reason: str) -> IntelligenceResult:
        result = IntelligenceResult(
            executive_summary="Local AI intelligence is temporarily unavailable.",
            channel_health={"status": "unknown"},
            degraded=True,
            warnings=[reason],
        )
        return self._confidence.score(result, context)
