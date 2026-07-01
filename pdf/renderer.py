"""Executive brief renderer for structured report JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .charts import ChartRenderer
from .images import ImageRenderer
from .tables import TableRenderer


@dataclass
class RenderStats:
    """Rendering counters used for logs and diagnostics."""

    tables_rendered: int = 0
    charts_rendered: int = 0
    images_rendered: int = 0
    warnings: list[str] = field(default_factory=list)


class ReportRenderer:
    """Convert report JSON into decision-focused executive PDF pages."""

    def __init__(self, table_renderer: TableRenderer, image_renderer: ImageRenderer, chart_renderer: ChartRenderer) -> None:
        self._table_renderer = table_renderer
        self._image_renderer = image_renderer
        self._chart_renderer = chart_renderer

    def render_sections(
        self,
        report_json: dict[str, Any],
        *,
        styles,
        max_width: float,
        report_type: str,
    ) -> tuple[list[Any], list[str], RenderStats, int]:
        """Render executive pages and return flowables, titles, stats, and page count."""

        flowables: list[Any] = []
        section_titles: list[str] = []
        stats = RenderStats()
        pages: list[list[Any]] = []

        page = self._build_ceo_brief_page(report_json, styles, max_width)
        if page:
            pages.append(page)
            section_titles.append("CEO Morning Brief")

        page = self._build_latest_video_page(report_json, styles, max_width, stats)
        if page:
            pages.append(page)
            section_titles.append("Latest Video Analysis")

        page = self._build_key_graphs_page(report_json, styles, max_width, stats)
        if page:
            pages.append(page)
            section_titles.append("Key Graphs")

        page = self._build_competitor_news_page(report_json, styles, max_width, stats)
        if page:
            pages.append(page)
            section_titles.append("Competitor + News Intelligence")

        page = self._build_action_plan_page(report_json, styles, max_width, stats)
        if page:
            pages.append(page)
            section_titles.append("Action Plan")

        page = self._build_prediction_page(report_json, styles, max_width)
        if page:
            pages.append(page)
            section_titles.append("Prediction Summary")

        page = self._build_assets_page(report_json, styles, max_width, stats)
        if page:
            pages.append(page)
            section_titles.append("Report Assets")

        if not pages:
            pages.append([Paragraph("No section data available in this report.", styles["BodyTextPro"])])

        _, max_pages = self._page_limits(report_type)
        pages = pages[:max_pages]

        for page_index, page_content in enumerate(pages):
            if page_index > 0:
                from reportlab.platypus import PageBreak

                flowables.append(PageBreak())
            flowables.extend(page_content)

        return flowables, section_titles, stats, len(pages)

    def _build_ceo_brief_page(self, report_json: dict[str, Any], styles, max_width: float) -> list[Any]:
        score = self._lookup(report_json, ["scores", "channel_health_score"]) or self._lookup(report_json, ["scores", "channel_health"])
        performance = self._find_text(report_json, ("overall_performance", "trend", "performance"), "Stable")
        biggest_win = self._find_text(report_json, ("biggest_win", "win"), "No major win detected")
        biggest_problem = self._find_text(report_json, ("biggest_problem", "risk", "problem"), "No major blocker detected")
        priority = self._find_text(report_json, ("highest_priority", "priority", "top_action"), "Publish the next high-intent video")
        upload_time = self._find_text(report_json, ("best_upload_time", "upload_time"), "Not available")
        opportunity = self._find_text(report_json, ("trending_opportunity", "opportunity", "trend"), "No immediate trend captured")
        prediction = self._find_text(report_json, ("highest_confidence_prediction", "prediction"), "No high-confidence prediction available")
        single_action = self._find_text(report_json, ("one_thing_to_do_today", "single_action", "action"), "Improve next thumbnail packaging")
        ai_summary = self._find_text(report_json, ("executive_summary", "summary"), "Focus on execution quality and publishing consistency.")

        cards = [
            ("Channel Health Score", str(score) if score is not None else "N/A"),
            ("Overall Performance", performance),
            ("Biggest Win", biggest_win),
            ("Biggest Problem", biggest_problem),
            ("Highest Priority Recommendation", priority),
            ("Best Upload Time Today", upload_time),
            ("Trending Opportunity", opportunity),
            ("Highest Confidence Prediction", prediction),
            ("One Thing To Do Today", single_action),
        ]

        page: list[Any] = [
            Paragraph("CEO Morning Brief", styles["SectionHeading"]),
            Spacer(1, 6),
            self._kpi_table(cards, styles, max_width),
            Spacer(1, 8),
            Paragraph("Today's AI Summary", styles["SubHeading"]),
            Paragraph(ai_summary, styles["RecommendationBox"]),
        ]
        return page

    def _build_latest_video_page(self, report_json: dict[str, Any], styles, max_width: float, stats: RenderStats) -> list[Any] | None:
        video_payload = self._first_section(report_json, ("latest_upload_analysis", "latest_video", "video_performance"))
        if video_payload is None:
            return None

        page: list[Any] = [Paragraph("Latest Video Analysis", styles["SectionHeading"])]

        thumbnail = self._find_image_payload(video_payload)
        if thumbnail is not None:
            self._render_image_payload(thumbnail, page, styles, max_width * 0.55, stats)

        metrics = self._build_metrics_rows(video_payload)
        if metrics:
            page.append(Spacer(1, 4))
            page.append(self._kpi_table(metrics, styles, max_width))

        page.extend(
            [
                Paragraph("What Worked", styles["SubHeading"]),
                Paragraph(self._find_text(video_payload, ("worked", "strength", "success"), "Not available."), styles["BodyTextPro"]),
                Paragraph("What Failed", styles["SubHeading"]),
                Paragraph(self._find_text(video_payload, ("failed", "weakness", "issue"), "Not available."), styles["BodyTextPro"]),
                Paragraph("Largest Audience Drop", styles["SubHeading"]),
                Paragraph(self._find_text(video_payload, ("largest_drop", "drop", "retention_drop"), "Not available."), styles["BodyTextPro"]),
                Paragraph("Why It Performed This Way", styles["SubHeading"]),
                Paragraph(self._find_text(video_payload, ("why", "explanation", "reason"), "Not available."), styles["BodyTextPro"]),
                Paragraph("One Improvement For Next Upload", styles["SubHeading"]),
                Paragraph(self._find_text(video_payload, ("improvement", "next_step", "recommendation"), "Not available."), styles["RecommendationBox"]),
            ]
        )
        return page

    def _build_key_graphs_page(self, report_json: dict[str, Any], styles, max_width: float, stats: RenderStats) -> list[Any] | None:
        graph_candidates = self._collect_graph_candidates(report_json)
        meaningful = [candidate for candidate in graph_candidates if self._is_meaningful_graph(candidate)]
        if not meaningful:
            return None

        page: list[Any] = [Paragraph("Key Graphs", styles["SectionHeading"])]
        for candidate in meaningful[:4]:
            page.append(Paragraph(str(candidate.get("title") or "Graph"), styles["SubHeading"]))
            self._render_chart_payload(candidate, page, styles, max_width, stats)
            page.append(Paragraph(f"Summary: {self._find_text(candidate, ('summary',), 'Not available.')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Largest increase: {self._find_text(candidate, ('largest_increase', 'max_increase'), 'Not available.')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Largest decrease: {self._find_text(candidate, ('largest_decrease', 'max_decrease'), 'Not available.')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Detected anomaly: {self._find_text(candidate, ('anomaly', 'outlier'), 'None')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Trend direction: {self._find_text(candidate, ('trend',), 'Unknown')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Key takeaway: {self._find_text(candidate, ('key_takeaway', 'takeaway'), 'Not available.')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"AI explanation: {self._find_text(candidate, ('ai_explanation', 'explanation'), 'Not available.')}", styles["BodyTextPro"]))
            page.append(Paragraph(f"Recommended action: {self._find_text(candidate, ('recommended_action', 'action'), 'Not available.')}", styles["RecommendationBox"]))
        return page

    def _build_competitor_news_page(
        self,
        report_json: dict[str, Any],
        styles,
        max_width: float,
        stats: RenderStats,
    ) -> list[Any] | None:
        competitors = self._first_section(report_json, ("competitor_intelligence", "competitors", "competitor_analysis"))
        news = self._first_section(report_json, ("news_intelligence", "news", "trending_topics"))
        if competitors is None and news is None:
            return None

        page: list[Any] = [Paragraph("Competitor + News Intelligence", styles["SectionHeading"])]

        if competitors is not None:
            page.append(Paragraph("Latest Competitor Uploads", styles["SubHeading"]))
            self._render_value(self._normalize_to_rows(competitors), page, styles, max_width, stats)
            page.append(Paragraph("Missed Opportunities", styles["SubHeading"]))
            page.append(Paragraph(self._find_text(competitors, ("missed_opportunities", "gaps"), "No significant missed opportunities identified."), styles["BodyTextPro"]))

        if news is not None:
            page.append(Paragraph("Trending Topics / Gaming News", styles["SubHeading"]))
            self._render_value(self._normalize_to_rows(news), page, styles, max_width, stats)
            page.append(Paragraph("Why This Matters", styles["SubHeading"]))
            page.append(Paragraph(self._find_text(news, ("why_it_matters", "impact"), "Not available."), styles["BodyTextPro"]))
            page.append(Paragraph("Matches Previous Winning Topics", styles["SubHeading"]))
            page.append(Paragraph(self._find_text(news, ("matches_previous_success", "topic_match"), "Not available."), styles["BodyTextPro"]))
            page.append(Paragraph("Competitor Topics Not Covered By This Channel", styles["SubHeading"]))
            page.append(Paragraph(self._find_text(news, ("competitor_gaps", "not_covered_topics"), "Not available."), styles["BodyTextPro"]))

        return page

    def _build_action_plan_page(self, report_json: dict[str, Any], styles, max_width: float, stats: RenderStats) -> list[Any] | None:
        action_plan = self._first_section(report_json, ("action_plan", "recommendations", "ai_intelligence"))
        if action_plan is None:
            return None

        page: list[Any] = [Paragraph("Action Plan", styles["SectionHeading"])]

        ranked_rows = self._extract_recommendations(action_plan)
        if ranked_rows:
            page.append(Paragraph("Ranked Recommendations", styles["SubHeading"]))
            table = self._table_renderer.render(ranked_rows, styles=styles, max_width=max_width)
            if table is not None:
                page.append(table)
                stats.tables_rendered += 1

        ideas = self._extract_video_ideas(report_json)
        if ideas:
            page.append(Spacer(1, 8))
            page.append(Paragraph("Top 5 Video Ideas", styles["SubHeading"]))
            table = self._table_renderer.render(ideas[:5], styles=styles, max_width=max_width)
            if table is not None:
                page.append(table)
                stats.tables_rendered += 1

        return page

    def _build_prediction_page(self, report_json: dict[str, Any], styles, max_width: float) -> list[Any] | None:
        predictions = self._first_section(report_json, ("predictions", "prediction_summary", "forecast"))
        if predictions is None:
            return None
        if not self._has_significant_change(predictions):
            return None

        page: list[Any] = [
            Paragraph("Prediction Summary", styles["SectionHeading"]),
            self._kpi_table(
                [
                    ("Future Views", self._find_text(predictions, ("future_views", "views"), "N/A")),
                    ("CTR Prediction", self._find_text(predictions, ("ctr_prediction", "ctr"), "N/A")),
                    ("Retention Prediction", self._find_text(predictions, ("retention_prediction", "retention"), "N/A")),
                    ("Subscriber Prediction", self._find_text(predictions, ("subscriber_prediction", "subscribers"), "N/A")),
                    ("Best Upload Time", self._find_text(predictions, ("best_upload_time", "upload_time"), "N/A")),
                    ("Expected Viral Probability", self._find_text(predictions, ("viral_probability", "virality"), "N/A")),
                ],
                styles,
                max_width,
            ),
        ]
        return page

    def _build_assets_page(self, report_json: dict[str, Any], styles, max_width: float, stats: RenderStats) -> list[Any] | None:
        assets = self._first_section(report_json, ("assets", "report_assets", "media_assets"))
        if assets is None:
            return None
        page: list[Any] = [Paragraph("Report Assets", styles["SectionHeading"])]
        self._render_value(assets, page, styles, max_width, stats)
        return page

    def _minimal_insight_page(self, report_json: dict[str, Any], styles) -> list[Any]:
        return [
            Paragraph("Executive Insight", styles["SectionHeading"]),
            Paragraph(
                self._find_text(report_json, ("executive_summary", "summary"), "Continue testing one high-impact idea today and track CTR and retention in the next 24 hours."),
                styles["BodyTextPro"],
            ),
        ]

    def _page_limits(self, report_type: str) -> tuple[int, int]:
        normalized = (report_type or "daily").lower()
        limits = {
            "daily": (5, 8),
            "weekly": (10, 15),
            "monthly": (15, 20),
            "comparison": (6, 12),
            "historical": (8, 15),
            "executive": (5, 8),
        }
        return limits.get(normalized, (5, 8))

    def _kpi_table(self, rows: list[tuple[str, str]], styles, max_width: float):
        body = [[Paragraph(label, styles["SubHeading"]), Paragraph(str(value), styles["BodyTextPro"])] for label, value in rows]
        table = Table(body, colWidths=[max_width * 0.38, max_width * 0.62])
        table.setStyle(
            TableStyle(
                [
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F7FAFD"), colors.white]),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C9D5E2")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DDE5EE")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return table

    def _build_metrics_rows(self, payload: Any) -> list[tuple[str, str]]:
        return [
            ("Title", self._find_text(payload, ("title",), "N/A")),
            ("Views", self._find_text(payload, ("views",), "N/A")),
            ("CTR", self._find_text(payload, ("ctr", "click_through_rate"), "N/A")),
            ("Retention", self._find_text(payload, ("retention",), "N/A")),
            ("Subscribers Gained", self._find_text(payload, ("subscribers_gained",), "N/A")),
            ("Watch Time", self._find_text(payload, ("watch_time", "watch_time_hours"), "N/A")),
            ("Traffic Sources", self._find_text(payload, ("traffic_sources",), "N/A")),
            ("Engagement", self._find_text(payload, ("engagement",), "N/A")),
        ]

    def _extract_recommendations(self, payload: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        items = []
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                items = payload["data"]
            elif isinstance(payload.get("action_plan"), list):
                items = payload["action_plan"]
        elif isinstance(payload, list):
            items = payload

        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "priority": item.get("priority", "medium"),
                    "reason": item.get("reason") or item.get("title") or item.get("action") or "N/A",
                    "expected_impact": item.get("expected_impact") or item.get("impact") or "N/A",
                    "difficulty": item.get("difficulty", "N/A"),
                    "estimated_time": item.get("estimated_time") or item.get("time") or "N/A",
                    "confidence": item.get("confidence", "N/A"),
                }
            )
        return rows

    def _extract_video_ideas(self, report_json: dict[str, Any]) -> list[dict[str, Any]]:
        idea_sources = []
        for key in ("video_ideas", "ideas", "ai_intelligence"):
            source = report_json.get(key)
            if source is not None:
                idea_sources.append(source)

        ideas: list[dict[str, Any]] = []
        for source in idea_sources:
            if isinstance(source, dict) and isinstance(source.get("video_ideas"), list):
                iterable = source["video_ideas"]
            elif isinstance(source, list):
                iterable = source
            else:
                continue
            for item in iterable:
                if not isinstance(item, dict):
                    continue
                ideas.append(
                    {
                        "title": item.get("title", "Untitled"),
                        "hook": item.get("hook", "N/A"),
                        "reason": item.get("reason", "N/A"),
                        "expected_performance": item.get("expected_performance") or item.get("expected_impact") or "N/A",
                        "difficulty": item.get("difficulty", "N/A"),
                        "confidence": item.get("confidence", "N/A"),
                        "thumbnail_concept": item.get("thumbnail_concept") or item.get("thumbnail") or "N/A",
                    }
                )
        return ideas

    def _collect_graph_candidates(self, report_json: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        stack = [report_json]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if self._is_chart_payload(current):
                    candidates.append(current)
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(current, list):
                for value in current:
                    if isinstance(value, (dict, list)):
                        stack.append(value)
        return candidates

    def _is_meaningful_graph(self, payload: dict[str, Any]) -> bool:
        return any(
            payload.get(key)
            for key in ("summary", "anomaly", "trend", "recommended_action", "ai_explanation", "key_takeaway")
        )

    def _has_significant_change(self, payload: Any) -> bool:
        text = str(payload).lower()
        indicators = ("significant", "spike", "drop", "surge", "high confidence", "reversal")
        return any(indicator in text for indicator in indicators)

    def _lookup(self, payload: Any, path: list[str]) -> Any:
        current = payload
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _first_section(self, payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in payload:
                value = payload[key]
                if isinstance(value, dict):
                    status = str(value.get("status", "available")).lower()
                    if status in {"unavailable", "missing", "skipped"}:
                        continue
                    if "data" in value:
                        return value["data"]
                return value
        return None

    def _find_text(self, payload: Any, keys: tuple[str, ...], default: str) -> str:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload and payload[key] not in (None, ""):
                    return str(payload[key])
            for value in payload.values():
                found = self._find_text(value, keys, default="")
                if found:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = self._find_text(value, keys, default="")
                if found:
                    return found
        return default

    def _find_image_payload(self, payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            if self._is_image_payload(payload):
                return payload
            for value in payload.values():
                found = self._find_image_payload(value)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = self._find_image_payload(value)
                if found is not None:
                    return found
        return None

    def _normalize_to_rows(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                return [item for item in payload["data"] if isinstance(item, dict)]
            return [{"summary": self._find_text(payload, ("summary", "title", "topic", "name"), str(payload))}]
        return [{"summary": str(payload)}]

    def _render_value(self, value: Any, flowables: list[Any], styles, max_width: float, stats: RenderStats) -> None:
        if value is None:
            flowables.append(Paragraph("-", styles["BodyTextPro"]))
            return

        if isinstance(value, (str, int, float, bool)):
            flowables.append(Paragraph(str(value), styles["BodyTextPro"]))
            return

        if isinstance(value, list):
            self._render_list(value, flowables, styles, max_width, stats)
            return

        if isinstance(value, dict):
            if self._is_chart_payload(value):
                self._render_chart_payload(value, flowables, styles, max_width, stats)
                return
            if self._is_image_payload(value):
                self._render_image_payload(value, flowables, styles, max_width, stats)
                return
            for sub_key, sub_value in value.items():
                flowables.append(Paragraph(sub_key.replace("_", " ").title(), styles["SubHeading"]))
                self._render_value(sub_value, flowables, styles, max_width, stats)
            return

        flowables.append(Paragraph(str(value), styles["BodyTextPro"]))

    def _render_list(self, values: list[Any], flowables: list[Any], styles, max_width: float, stats: RenderStats) -> None:
        if not values:
            flowables.append(Paragraph("No rows available.", styles["Muted"]))
            return

        if all(isinstance(item, dict) for item in values):
            table = self._table_renderer.render(values, styles=styles, max_width=max_width)
            if table is not None:
                stats.tables_rendered += 1
                flowables.append(table)
                flowables.append(Spacer(1, 6))
                return

        for item in values:
            self._render_value(item, flowables, styles, max_width, stats)

    def _render_chart_payload(self, payload: dict[str, Any], flowables: list[Any], styles, max_width: float, stats: RenderStats) -> None:
        chart_path = payload.get("chart_path") or payload.get("image_path")
        caption = payload.get("caption")
        if not chart_path:
            stats.warnings.append("Chart payload missing chart_path")
            flowables.append(Paragraph("Missing chart path.", styles["WarningBox"]))
            return
        try:
            flowables.append(self._chart_renderer.render(chart_path, caption, styles=styles, max_width=max_width))
            stats.charts_rendered += 1
        except Exception as exc:
            stats.warnings.append(str(exc))
            flowables.append(Paragraph(str(exc), styles["WarningBox"]))

    def _render_image_payload(self, payload: dict[str, Any], flowables: list[Any], styles, max_width: float, stats: RenderStats) -> None:
        image_path = payload.get("image_path") or payload.get("thumbnail_path") or payload.get("logo_path")
        if not image_path:
            stats.warnings.append("Image payload missing image_path")
            flowables.extend(self._image_renderer.placeholder("Image path is missing.", styles))
            return
        try:
            flowables.append(self._image_renderer.render(image_path, max_width=max_width, max_height=220, styles=styles))
            flowables.append(Spacer(1, 8))
            stats.images_rendered += 1
        except Exception as exc:
            stats.warnings.append(str(exc))
            flowables.extend(self._image_renderer.placeholder(str(exc), styles))

    def _is_chart_payload(self, payload: dict[str, Any]) -> bool:
        return any(key in payload for key in ("chart_path", "caption")) and any(
            key in payload for key in ("chart_path", "image_path")
        )

    def _is_image_payload(self, payload: dict[str, Any]) -> bool:
        image_keys = {"image_path", "thumbnail_path", "logo_path"}
        return any(key in payload for key in image_keys)
