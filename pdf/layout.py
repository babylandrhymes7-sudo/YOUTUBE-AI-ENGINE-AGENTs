"""Page layout primitives for PDF generation."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4


@dataclass(frozen=True)
class LayoutManager:
    """Centralize page geometry, margins, and spacing values."""

    page_size: tuple[float, float] = A4
    margin_top: float = 54.0
    margin_right: float = 48.0
    margin_bottom: float = 54.0
    margin_left: float = 48.0
    section_spacing: float = 14.0
    paragraph_spacing: float = 8.0

    @property
    def content_width(self) -> float:
        """Printable width after horizontal margins."""

        return self.page_size[0] - self.margin_left - self.margin_right

    @property
    def content_height(self) -> float:
        """Printable height after vertical margins."""

        return self.page_size[1] - self.margin_top - self.margin_bottom
