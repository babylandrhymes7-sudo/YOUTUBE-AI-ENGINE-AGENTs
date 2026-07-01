"""Document builder for executive PDF output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

from app.logging import get_logger

from .exceptions import DiskWriteError, RenderFailureError
from .footer import FooterRenderer
from .header import HeaderRenderer
from .layout import LayoutManager
from .templates import PDFTemplateContext


logger = get_logger(__name__)


@dataclass(frozen=True)
class DocumentBuildResult:
    """Result emitted by DocumentBuilder after rendering."""

    output_path: Path
    pages_generated: int
    render_seconds: float


class _ExecutiveDocTemplate(BaseDocTemplate):
    """Track page count while building the document."""

    def __init__(self, filename: str, **kwargs: Any) -> None:
        super().__init__(filename, **kwargs)
        self.pages_generated = 0

    def afterPage(self) -> None:  # noqa: N802 - ReportLab callback name
        self.pages_generated += 1


class DocumentBuilder:
    """Create ReportLab document templates and stream flowables to disk."""

    def __init__(
        self,
        layout_manager: LayoutManager,
        header_renderer: HeaderRenderer,
        footer_renderer: FooterRenderer,
    ) -> None:
        self._layout = layout_manager
        self._header = header_renderer
        self._footer = footer_renderer

    def build(
        self,
        output_path: Path,
        *,
        story: list[Any],
        context: PDFTemplateContext,
    ) -> DocumentBuildResult:
        """Render a full PDF document to local disk."""

        started = perf_counter()
        try:
            document = _ExecutiveDocTemplate(
                str(output_path),
                pagesize=self._layout.page_size,
                leftMargin=self._layout.margin_left,
                rightMargin=self._layout.margin_right,
                topMargin=self._layout.margin_top,
                bottomMargin=self._layout.margin_bottom,
            )
            frame = Frame(
                self._layout.margin_left,
                self._layout.margin_bottom,
                self._layout.content_width,
                self._layout.content_height,
                id="main-frame",
            )
            template = PageTemplate(id="main", frames=[frame], onPage=lambda c, d: self._on_page(c, d, context))
            document.addPageTemplates([template])
            document.build(story)
        except OSError as exc:
            raise DiskWriteError(f"Failed writing PDF to disk: {output_path}") from exc
        except Exception as exc:  # pragma: no cover - ReportLab internals vary
            raise RenderFailureError(f"PDF rendering failed: {exc}") from exc

        elapsed = perf_counter() - started
        logger.info(
            "PDF built output=%s pages=%s duration=%.3fs",
            output_path,
            document.pages_generated,
            elapsed,
        )
        return DocumentBuildResult(
            output_path=output_path,
            pages_generated=document.pages_generated,
            render_seconds=elapsed,
        )

    def _on_page(self, canvas, doc, context: PDFTemplateContext) -> None:
        width, height = self._layout.page_size
        self._set_metadata(canvas, context)
        self._header.draw(canvas, context, width, height)
        self._footer.draw(canvas, context, width)

    def _set_metadata(self, canvas, context: PDFTemplateContext) -> None:
        if getattr(canvas, "_pdf_metadata_set", False):
            return
        canvas.setTitle(context.title)
        canvas.setAuthor(context.author)
        canvas.setSubject(f"{context.report_type.title()} Intelligence Report")
        canvas.setCreator(context.generator)
        canvas.setKeywords(
            f"report_type={context.report_type},version={context.report_version},app={context.application_version},model={context.model_version}"
        )
        setattr(canvas, "_pdf_metadata_set", True)
