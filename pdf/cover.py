"""Cover page renderer."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .templates import PDFTemplateContext


class CoverRenderer:
    """Build first-page cover elements for the executive report."""

    def build(self, styles, context: PDFTemplateContext):
        return [
            Spacer(1, 36 * mm),
            Paragraph(context.title, styles["ExecutiveTitle"]),
            Spacer(1, 6 * mm),
            Paragraph(f"Report Type: {context.report_type.title()}", styles["SubHeading"]),
            Paragraph(f"Prepared For: {context.author}", styles["BodyTextPro"]),
            Paragraph(f"Generated At: {context.generated_at:%Y-%m-%d %H:%M %Z}", styles["BodyTextPro"]),
            Spacer(1, 8 * mm),
            Paragraph("Confidential - Local Use Only", styles["WarningBox"]),
            Spacer(1, 40 * mm),
            Paragraph("YOUTUBE AI AGENT", styles["Muted"]),
            Paragraph(
                f"Generator: {context.generator} | App: {context.application_version} | Model: {context.model_version}",
                styles["Muted"],
            ),
        ]
