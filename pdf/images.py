"""Image rendering helpers for PDF sections."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from .exceptions import MissingImageError


class ImageRenderer:
    """Scale, align, and safely render image assets."""

    def render(self, image_path: str | Path, *, max_width: float, max_height: float, styles):
        path = Path(image_path)
        if not path.exists():
            raise MissingImageError(f"Image not found: {path}")
        image = Image(str(path))
        image._restrictSize(max_width, max_height)
        return image

    def placeholder(self, message: str, styles):
        table = Table([[Paragraph(message, styles["Muted"])]], colWidths=[120 * mm], rowHeights=[20 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#C9D5E2")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F8FB")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return [table, Spacer(1, 6)]
