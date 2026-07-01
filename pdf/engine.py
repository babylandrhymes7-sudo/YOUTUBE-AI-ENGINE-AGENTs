"""Main orchestrator for local PDF generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.logging import get_logger

from .charts import ChartRenderer
from .document import DocumentBuildResult, DocumentBuilder
from .exceptions import InvalidReportJSONError
from .footer import FooterRenderer
from .header import HeaderRenderer
from .images import ImageRenderer
from .layout import LayoutManager
from .renderer import RenderStats, ReportRenderer
from .styles import StyleManager
from .tables import TableRenderer
from .templates import resolve_context
from .utils import archive_previous_reports, resolve_output_path


logger = get_logger(__name__)


@dataclass(frozen=True)
class PDFEngineResult:
    """Final PDF generation output and telemetry."""

    output_path: Path
    pages_generated: int
    tables_rendered: int
    charts_rendered: int
    images_rendered: int
    warnings: list[str]
    render_seconds: float


class PDFEngine:
    """Render validated report JSON into a professional local PDF."""

    def __init__(
        self,
        *,
        output_dir: str | Path = Path("storage") / "reports",
        app_version: str = "1.0.0",
        model_version: str = "qwen3.5",
        layout_manager: LayoutManager | None = None,
        style_manager: StyleManager | None = None,
        document_builder: DocumentBuilder | None = None,
        report_renderer: ReportRenderer | None = None,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._app_version = app_version
        self._model_version = model_version

        self._layout = layout_manager or LayoutManager()
        self._style_manager = style_manager or StyleManager()

        header_renderer = HeaderRenderer()
        footer_renderer = FooterRenderer()
        self._document_builder = document_builder or DocumentBuilder(self._layout, header_renderer, footer_renderer)

        image_renderer = ImageRenderer()
        table_renderer = TableRenderer()
        chart_renderer = ChartRenderer(image_renderer)
        self._report_renderer = report_renderer or ReportRenderer(table_renderer, image_renderer, chart_renderer)

    def generate(self, report_json: dict[str, Any], *, overwrite: bool = False) -> PDFEngineResult:
        """Render one report payload into a local versioned PDF file."""

        self._validate_report_json(report_json)
        context = resolve_context(report_json, app_version=self._app_version, model_version=self._model_version)
        archive_previous_reports(self._output_dir, context.report_type, context.generated_at)
        output_path = resolve_output_path(
            self._output_dir,
            context.report_type,
            context.generated_at,
            overwrite=overwrite,
        )

        logger.info("Starting PDF creation report_type=%s output=%s", context.report_type, output_path)

        styles = self._style_manager.build()
        section_flowables, section_titles, stats, planned_pages = self._report_renderer.render_sections(
            report_json,
            styles=styles,
            max_width=self._layout.content_width,
            report_type=context.report_type,
        )

        story: list[Any] = list(section_flowables)

        build_result = self._document_builder.build(output_path, story=story, context=context)
        self._log_result(build_result, stats, output_path, section_titles, planned_pages)

        return PDFEngineResult(
            output_path=output_path,
            pages_generated=build_result.pages_generated,
            tables_rendered=stats.tables_rendered,
            charts_rendered=stats.charts_rendered,
            images_rendered=stats.images_rendered,
            warnings=stats.warnings,
            render_seconds=build_result.render_seconds,
        )

    def _validate_report_json(self, report_json: dict[str, Any]) -> None:
        if not isinstance(report_json, dict):
            raise InvalidReportJSONError("Report payload must be a dictionary")
        if not report_json:
            raise InvalidReportJSONError("Report payload is empty")
        report_type = report_json.get("report_type")
        if report_type is not None and not isinstance(report_type, str):
            raise InvalidReportJSONError("report_type must be a string")

    def _log_result(
        self,
        build_result: DocumentBuildResult,
        stats: RenderStats,
        output_path: Path,
        section_titles: list[str],
        planned_pages: int,
    ) -> None:
        logger.info(
            "PDF creation completed output=%s pages=%s planned_pages=%s sections=%s tables=%s charts=%s images=%s warnings=%s duration=%.3fs",
            output_path,
            build_result.pages_generated,
            planned_pages,
            section_titles,
            stats.tables_rendered,
            stats.charts_rendered,
            stats.images_rendered,
            len(stats.warnings),
            build_result.render_seconds,
        )
        for warning in stats.warnings:
            logger.warning("PDF rendering warning: %s", warning)
