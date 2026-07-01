"""Typography and visual style catalog for executive PDFs."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet

from .exceptions import InvalidFontError


@dataclass
class StyleManager:
    """Provide consistent paragraph and table styling across the PDF."""

    base_font: str = "Helvetica"
    heading_font: str = "Helvetica-Bold"

    def build(self) -> StyleSheet1:
        """Return a style sheet customized for executive report rendering."""

        if not self.base_font or not self.heading_font:
            raise InvalidFontError("Font names cannot be empty")

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="ExecutiveTitle",
                parent=styles["Title"],
                fontName=self.heading_font,
                fontSize=26,
                leading=30,
                textColor=colors.HexColor("#0E1A2B"),
                spaceAfter=18,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionHeading",
                parent=styles["Heading2"],
                fontName=self.heading_font,
                fontSize=15,
                leading=18,
                textColor=colors.HexColor("#143A5A"),
                spaceBefore=14,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SubHeading",
                parent=styles["Heading3"],
                fontName=self.heading_font,
                fontSize=11,
                leading=14,
                textColor=colors.HexColor("#1C4E80"),
                spaceBefore=10,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="BodyTextPro",
                parent=styles["BodyText"],
                fontName=self.base_font,
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor("#1D2430"),
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Muted",
                parent=styles["BodyText"],
                fontName=self.base_font,
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#5E6A78"),
            )
        )
        styles.add(
            ParagraphStyle(
                name="WarningBox",
                parent=styles["BodyText"],
                fontName=self.base_font,
                fontSize=9,
                backColor=colors.HexColor("#FFF4E5"),
                borderColor=colors.HexColor("#F4B183"),
                borderWidth=0.8,
                borderPadding=6,
                textColor=colors.HexColor("#7A4E00"),
                leading=12,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="RecommendationBox",
                parent=styles["BodyText"],
                fontName=self.base_font,
                fontSize=9,
                backColor=colors.HexColor("#EAF6FF"),
                borderColor=colors.HexColor("#99C3E8"),
                borderWidth=0.8,
                borderPadding=6,
                textColor=colors.HexColor("#1F4D73"),
                leading=12,
                spaceAfter=8,
            )
        )
        return styles
