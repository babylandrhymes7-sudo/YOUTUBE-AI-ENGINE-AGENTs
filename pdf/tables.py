"""Table rendering helpers for structured report data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle


class TableRenderer:
    """Render report tables with wrapping, striping, and pagination support."""

    def render(self, rows: Sequence[Mapping[str, object]], *, styles, max_width: float):
        if not rows:
            return None

        columns = list(rows[0].keys())
        body = [columns]
        for row in rows:
            body.append([self._cell(row.get(column), styles) for column in columns])

        col_width = max_width / max(len(columns), 1)
        table = Table(body, colWidths=[col_width] * len(columns), repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#143A5A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D5E2")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F7FAFD")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    def _cell(self, value: object, styles):
        if isinstance(value, (int, float)):
            return f"{value}"
        if value is None:
            return "-"
        return Paragraph(str(value), styles["BodyTextPro"])
