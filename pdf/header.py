"""Header drawing primitives."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

from .templates import PDFTemplateContext


class HeaderRenderer:
    """Render a concise executive header on every page."""

    def draw(self, canvas: Canvas, context: PDFTemplateContext, page_width: float, page_height: float) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5DFEA"))
        canvas.setLineWidth(0.6)
        canvas.line(42, page_height - 42, page_width - 42, page_height - 42)
        canvas.setFillColor(colors.HexColor("#1F4D73"))
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(42, page_height - 35, "YOUTUBE AI AGENT")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5E6A78"))
        canvas.drawRightString(page_width - 42, page_height - 35, context.report_type.upper())
        canvas.restoreState()
