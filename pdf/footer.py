"""Footer drawing primitives."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

from .templates import PDFTemplateContext


class FooterRenderer:
    """Render page numbering and generation details on each page."""

    def draw(self, canvas: Canvas, context: PDFTemplateContext, page_width: float) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5DFEA"))
        canvas.setLineWidth(0.6)
        canvas.line(42, 38, page_width - 42, 38)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#5E6A78"))
        canvas.drawString(42, 28, f"Generated: {context.generated_at:%Y-%m-%d %H:%M %Z} | Version: {context.report_version}")
        canvas.drawRightString(page_width - 42, 28, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
