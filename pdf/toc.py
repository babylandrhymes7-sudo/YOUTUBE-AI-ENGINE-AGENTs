"""Table-of-contents renderer."""

from __future__ import annotations

from reportlab.platypus import ListFlowable, ListItem, Paragraph, Spacer


class TOCRenderer:
    """Render a lightweight static table of contents from section titles."""

    def build(self, styles, section_titles: list[str]):
        items = [ListItem(Paragraph(title, styles["BodyTextPro"])) for title in section_titles]
        return [
            Paragraph("Table of Contents", styles["SectionHeading"]),
            ListFlowable(items, bulletType="1", start="1"),
            Spacer(1, 12),
        ]
