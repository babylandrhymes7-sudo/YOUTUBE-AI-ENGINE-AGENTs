"""Chart placement renderer."""

from __future__ import annotations

from pathlib import Path

from reportlab.platypus import KeepTogether, Paragraph, Spacer

from .exceptions import MissingChartError
from .images import ImageRenderer


class ChartRenderer:
    """Render chart images with captions and safe fallback behavior."""

    def __init__(self, image_renderer: ImageRenderer) -> None:
        self._image_renderer = image_renderer

    def render(self, chart_path: str | Path, caption: str | None, *, styles, max_width: float):
        path = Path(chart_path)
        if not path.exists():
            raise MissingChartError(f"Chart not found: {path}")
        chart = self._image_renderer.render(path, max_width=max_width, max_height=260, styles=styles)
        content = [chart]
        if caption:
            content.append(Spacer(1, 4))
            content.append(Paragraph(caption, styles["Muted"]))
        content.append(Spacer(1, 8))
        return KeepTogether(content)
