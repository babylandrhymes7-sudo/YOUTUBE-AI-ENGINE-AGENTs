"""Notification delivery coordination."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.logging import get_logger

from .alerts import AlertManager
from .base import NotificationProvider
from .contracts import (
    NotificationAttachment,
    NotificationCategory,
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationMessage,
    NotificationOutcome,
    NotificationPriority,
)
from .logger import NotificationLogger
from .queue import NotificationQueue, QueuedNotification
from .retry import RetryManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class DeliveryContext:
    notification: NotificationMessage
    provider_name: str
    delivered: bool


class NotificationValidationError(ValueError):
    """Raised when a notification payload is invalid."""


class NotificationManager:
    def __init__(
        self,
        providers: list[NotificationProvider],
        *,
        queue: NotificationQueue | None = None,
        retry_manager: RetryManager | None = None,
        alert_manager: AlertManager | None = None,
        sent_ledger_path: Path | None = None,
        logger_service: NotificationLogger | None = None,
    ) -> None:
        self._providers = {provider.name: provider for provider in providers}
        self._queue = queue or NotificationQueue(settings.notification_state_dir / "queue.json")
        self._retry = retry_manager or RetryManager(settings.notification_retry_attempts, settings.notification_retry_delay_seconds)
        self._alert_manager = alert_manager or AlertManager(
            min_confidence=settings.instant_alert_min_confidence,
            min_impact=settings.instant_alert_min_impact,
            min_delta_percent=settings.instant_alert_min_delta_percent,
        )
        self._sent_ledger_path = sent_ledger_path or (settings.notification_state_dir / "sent_notifications.json")
        self._sent_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logger_service or NotificationLogger()

    def send_daily_brief(self, report: dict[str, Any], pdf_path: str | Path | None, *, generation_seconds: float | None = None) -> NotificationOutcome:
        message = self._build_brief(
            NotificationCategory.DAILY_MORNING_BRIEF,
            report,
            pdf_path,
            generation_seconds=generation_seconds,
        )
        return self.dispatch(message)

    def send_weekly_brief(self, report: dict[str, Any], pdf_path: str | Path | None, *, generation_seconds: float | None = None) -> NotificationOutcome:
        message = self._build_brief(
            NotificationCategory.WEEKLY_STRATEGY_BRIEF,
            report,
            pdf_path,
            generation_seconds=generation_seconds,
        )
        return self.dispatch(message)

    def send_monthly_brief(self, report: dict[str, Any], pdf_path: str | Path | None, *, generation_seconds: float | None = None) -> NotificationOutcome:
        message = self._build_brief(
            NotificationCategory.MONTHLY_REPORT_BRIEF,
            report,
            pdf_path,
            generation_seconds=generation_seconds,
        )
        return self.dispatch(message)

    def send_news_update(self, news_analysis: dict[str, Any]) -> NotificationOutcome:
        """Send a news-only alert built from AI-analyzed web/news updates."""

        message = self._build_news_update(news_analysis)
        return self.dispatch(message)

    def send_instant_alert(self, event: dict[str, Any]) -> NotificationOutcome:
        decision = self._alert_manager.evaluate(event)
        if not decision.should_notify or decision.message is None:
            return NotificationOutcome(
                notification_id=self._notification_id(event),
                category=NotificationCategory.INSTANT_AI_ALERT,
                title="Opportunity Detected",
                delivered=False,
                skipped_reason=decision.reason,
            )
        return self.dispatch(decision.message)

    def retry_failed(self) -> list[NotificationOutcome]:
        outcomes: list[NotificationOutcome] = []
        for queued in self._queue.dequeue_ready():
            payload = queued.payload
            message = self._message_from_payload(payload)
            outcomes.append(self.dispatch(message, notification_id_override=queued.notification_id))
        return outcomes

    def dispatch(self, message: NotificationMessage, *, notification_id_override: str | None = None) -> NotificationOutcome:
        message = self._ensure_message(message, notification_id_override=notification_id_override)
        if self._already_sent(message.notification_id):
            return NotificationOutcome(
                notification_id=message.notification_id,
                category=message.category,
                title=message.title,
                delivered=False,
                skipped_reason="duplicate notification",
            )

        validation_warnings = self._validate_message(message)
        provider_results: list[NotificationDeliveryResult] = []
        delivered_any = False
        attachment_retry_requested = self._attachment_retry_requested(message)
        for provider in self._providers.values():
            result = self._deliver_with_retry(provider, message)
            provider_results.append(result)
            delivered_any = delivered_any or result.success
            if not result.success:
                self._queue.enqueue(
                    QueuedNotification(
                        notification_id=message.notification_id,
                        provider=provider.name,
                        payload=message.to_dict(),
                        attempts=result.retries,
                        next_retry_at=self._next_retry_timestamp(),
                    )
                )
        if delivered_any:
            self._mark_sent(message.notification_id)
        if delivered_any and attachment_retry_requested:
            self._queue.enqueue(
                QueuedNotification(
                    notification_id=f"{message.notification_id}:attachment",
                    provider="attachment",
                    payload=message.to_dict(),
                    attempts=0,
                    next_retry_at=self._next_retry_timestamp(),
                )
            )
        outcome = NotificationOutcome(
            notification_id=message.notification_id,
            category=message.category,
            title=message.title,
            delivered=delivered_any,
            provider_results=tuple(provider_results),
            queued=not delivered_any or attachment_retry_requested,
            warnings=tuple(validation_warnings),
        )
        self._log_delivery(message, outcome)
        return outcome

    def _build_brief(
        self,
        category: NotificationCategory,
        report: dict[str, Any],
        pdf_path: str | Path | None,
        *,
        generation_seconds: float | None = None,
    ) -> NotificationMessage:
        self._validate_report(report, category)
        title = {
            NotificationCategory.DAILY_MORNING_BRIEF: "Daily Morning Brief",
            NotificationCategory.WEEKLY_STRATEGY_BRIEF: "Weekly Strategy Brief",
            NotificationCategory.MONTHLY_REPORT_BRIEF: "Monthly Channel Report",
        }.get(category, "Channel Report")
        brief = self._summarize_brief(report, category, generation_seconds=generation_seconds)
        attachments, payload_data = self._resolve_attachments(pdf_path)
        body = "\n".join(
            [
                f"Channel Health Score: {brief['channel_health_score']}",
                f"Executive Summary: {brief['executive_summary']}",
                f"Biggest Win: {brief['biggest_win']}",
                f"Biggest Problem: {brief['biggest_problem']}",
                f"Highest Priority Recommendation: {brief['highest_priority_recommendation']}",
                f"Best Upload Time Today: {brief['best_upload_time_today']}",
                f"Best Video Idea: {brief['best_video_idea']}",
                f"AI Confidence: {brief['ai_confidence']}",
                f"Report Generation Time: {brief['report_generation_time']}",
            ]
        )
        if category is NotificationCategory.WEEKLY_STRATEGY_BRIEF:
            body = body.replace("Best Upload Time Today", "Best Upload Time This Week")
        if category is NotificationCategory.MONTHLY_REPORT_BRIEF:
            body = body.replace("Best Upload Time Today", "Best Upload Time This Month")
        notification_id = self._notification_id({"category": category.value, "report_id": report.get("report_id"), "version": report.get("version"), "pdf": str(pdf_path) if pdf_path else None})
        return NotificationMessage(
            notification_id=notification_id,
            category=category,
            title=title,
            summary=brief["executive_summary"],
            body=body,
            data={"report": report, "brief": brief, **payload_data},
            attachments=attachments,
            priority=NotificationPriority.HIGH,
            confidence=brief["ai_confidence_value"],
            open_path=Path(pdf_path) if pdf_path else None,
        )

    def _build_news_update(self, news_analysis: dict[str, Any]) -> NotificationMessage:
        if not isinstance(news_analysis, dict) or not news_analysis:
            raise NotificationValidationError("news_analysis payload is required")
        summary = self._first_text(news_analysis, "executive_summary", "summary", "headline") or "Latest gaming news update is ready."
        articles = news_analysis.get("articles") if isinstance(news_analysis.get("articles"), list) else []
        opportunities = news_analysis.get("opportunities") if isinstance(news_analysis.get("opportunities"), list) else []
        threats = news_analysis.get("threats") if isinstance(news_analysis.get("threats"), list) else []
        action_plan = news_analysis.get("action_plan") if isinstance(news_analysis.get("action_plan"), list) else []
        confidence = self._float_first(news_analysis, "confidence")
        if confidence is None:
            confidence = self._float_first(news_analysis, "confidence_scores", "overall")
        if confidence is None:
            confidence = 0.0
        body = "\n".join(
            [
                f"News Summary: {summary}",
                f"Top Story: {self._best_item(articles)}",
                f"Opportunity: {self._best_item(opportunities)}",
                f"Threat: {self._best_item(threats)}",
                f"Recommended Action: {self._best_item(action_plan)}",
                f"AI Confidence: {round(confidence * 100)}%",
            ]
        )
        notification_id = self._notification_id(
            {
                "category": NotificationCategory.NEWS_UPDATE.value,
                "summary": summary,
                "articles": [
                    item.get("url") or item.get("title") if isinstance(item, dict) else str(item)
                    for item in articles[:5]
                ],
            }
        )
        return NotificationMessage(
            notification_id=notification_id,
            category=NotificationCategory.NEWS_UPDATE,
            title="Latest Gaming News Update",
            summary=summary,
            body=body,
            data={"news_analysis": news_analysis},
            priority=NotificationPriority.HIGH,
            confidence=confidence,
        )

    def _summarize_brief(self, report: dict[str, Any], category: NotificationCategory, *, generation_seconds: float | None = None) -> dict[str, Any]:
        document = report.get("document") if isinstance(report.get("document"), dict) else report
        scores = report.get("scores") if isinstance(report.get("scores"), dict) else {}
        metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
        summary = self._first_text(document, "executive_summary", "summary") or self._first_text(report, "executive_summary") or "No executive summary available."
        biggest_win = self._best_item(document.get("growth_opportunities") or document.get("key_findings") or report.get("growth_opportunities"))
        biggest_problem = self._best_item(document.get("threats") or report.get("threats") or report.get("warnings"))
        recommendation = self._best_item(document.get("action_plan") or report.get("action_plan"))
        best_video_idea = self._best_item(document.get("video_ideas") or report.get("video_ideas"))
        best_upload_time = self._first_text(metadata, "best_upload_time_today", "best_upload_time") or self._first_text(report, "best_upload_time_today") or "Not available"
        confidence = self._float_first(document, "confidence_scores", "overall")
        if confidence is None:
            confidence = self._float_first(report, "confidence")
        if confidence is None:
            confidence = 0.0
        generation_time = generation_seconds if generation_seconds is not None else self._float_first(report, "generation_seconds")
        if generation_time is None:
            generation_time = self._float_first(metadata, "report_generation_time_seconds")
        return {
            "channel_health_score": self._channel_health_score(report, scores),
            "executive_summary": summary,
            "biggest_win": biggest_win,
            "biggest_problem": biggest_problem,
            "highest_priority_recommendation": recommendation,
            "best_upload_time_today": best_upload_time if category is NotificationCategory.DAILY_MORNING_BRIEF else self._first_text(metadata, "best_upload_time_this_week", "best_upload_time_today") or best_upload_time,
            "best_video_idea": best_video_idea,
            "ai_confidence": f"{round(confidence * 100)}%",
            "ai_confidence_value": confidence,
            "report_generation_time": f"{round(generation_time, 2)}s" if generation_time is not None else "Not available",
        }

    def _channel_health_score(self, report: dict[str, Any], scores: dict[str, Any]) -> str:
        score = scores.get("channel_health_score") or scores.get("channel_health")
        if score is None and isinstance(report.get("channel_health"), dict):
            score = report["channel_health"].get("score") or report["channel_health"].get("value")
        return f"{round(float(score))}%" if score is not None else "Not available"

    def _validate_report(self, report: dict[str, Any], category: NotificationCategory) -> None:
        if not isinstance(report, dict) or not report:
            raise NotificationValidationError("report payload is required")
        report_type = str(report.get("report_type") or report.get("type") or "")
        expected = {
            NotificationCategory.DAILY_MORNING_BRIEF: "daily",
            NotificationCategory.WEEKLY_STRATEGY_BRIEF: "weekly",
            NotificationCategory.MONTHLY_REPORT_BRIEF: "monthly",
        }.get(category)
        if expected and report_type and report_type != expected:
            raise NotificationValidationError(f"report_type must be '{expected}' for {category.value}")

    def _validate_message(self, message: NotificationMessage) -> list[str]:
        warnings: list[str] = []
        if message.category in {NotificationCategory.DAILY_MORNING_BRIEF, NotificationCategory.WEEKLY_STRATEGY_BRIEF, NotificationCategory.MONTHLY_REPORT_BRIEF}:
            if not message.attachments and not message.data.get("pending_attachment_path"):
                warnings.append("pdf attachment is missing; summary will still be sent")
            for attachment in message.attachments:
                self._validate_attachment(attachment)
                if not attachment.path.exists():
                    warnings.append(f"attachment missing: {attachment.path}")
        return warnings

    def _validate_attachment(self, attachment: NotificationAttachment) -> None:
        if attachment.path.suffix.lower() != ".pdf" and attachment.mime_type == "application/pdf":
            raise NotificationValidationError("PDF attachment must use a .pdf path")
        if attachment.path.exists() and attachment.path.stat().st_size > settings.notification_max_attachment_size_mb * 1024 * 1024:
            raise NotificationValidationError("attachment exceeds configured size limit")
        if attachment.sha256 and attachment.path.exists():
            digest = hashlib.sha256(attachment.path.read_bytes()).hexdigest()
            if digest != attachment.sha256:
                raise NotificationValidationError("attachment integrity check failed")

    def _resolve_attachments(self, pdf_path: str | Path | None) -> tuple[tuple[NotificationAttachment, ...], dict[str, Any]]:
        if pdf_path is None:
            return (), {}
        path = Path(pdf_path)
        if path.exists():
            return (NotificationAttachment(path=path, filename=path.name, mime_type="application/pdf"),), {}
        return (), {"pending_attachment_path": str(path)}

    def _deliver_with_retry(self, provider: NotificationProvider, message: NotificationMessage) -> NotificationDeliveryResult:
        last_result: NotificationDeliveryResult | None = None

        def call() -> NotificationDeliveryResult:
            nonlocal last_result
            result = provider.send(message)
            last_result = result
            if not result.success:
                raise RuntimeError(result.error or "notification delivery failed")
            return result

        try:
            result, retries = self._retry.run(call)
            return NotificationDeliveryResult(
                provider=provider.name,
                channel=self._channel_for_provider(provider.name),
                notification_id=message.notification_id,
                success=result.success,
                retries=retries,
                warnings=result.warnings,
                error=result.error,
                attachment_sent=result.attachment_sent,
                recipient=result.recipient,
            )
        except Exception as exc:
            failed = last_result or NotificationDeliveryResult(
                provider=provider.name,
                channel=self._channel_for_provider(provider.name),
                notification_id=message.notification_id,
                success=False,
                error=str(exc),
            )
            return NotificationDeliveryResult(
                provider=provider.name,
                channel=failed.channel,
                notification_id=message.notification_id,
                success=False,
                retries=max(self._retry.attempts - 1, 0),
                warnings=failed.warnings,
                error=failed.error or str(exc),
                attachment_sent=failed.attachment_sent,
                recipient=failed.recipient,
            )

    def _channel_for_provider(self, provider_name: str) -> NotificationChannel:
        return {
            "telegram": NotificationChannel.TELEGRAM,
            "email": NotificationChannel.EMAIL,
            "desktop": NotificationChannel.DESKTOP,
        }.get(provider_name, NotificationChannel.DESKTOP)

    def _ensure_message(self, message: NotificationMessage, *, notification_id_override: str | None = None) -> NotificationMessage:
        if notification_id_override is None:
            return message
        return NotificationMessage(
            notification_id=notification_id_override,
            category=message.category,
            title=message.title,
            summary=message.summary,
            body=message.body,
            data=message.data,
            attachments=message.attachments,
            priority=message.priority,
            confidence=message.confidence,
            recipient=message.recipient,
            open_path=message.open_path,
        )

    def _message_from_payload(self, payload: dict[str, Any]) -> NotificationMessage:
        pending_path = payload.get("data", {}).get("pending_attachment_path")
        attachments = tuple(
            NotificationAttachment(path=Path(item["path"]), filename=item.get("filename"), mime_type=item.get("mime_type", "application/octet-stream"), sha256=item.get("sha256"))
            for item in payload.get("attachments", [])
        )
        if pending_path:
            path = Path(str(pending_path))
            if path.exists():
                attachments = attachments + (NotificationAttachment(path=path, filename=path.name, mime_type="application/pdf"),)
        return NotificationMessage(
            notification_id=str(payload["notification_id"]),
            category=NotificationCategory(payload["category"]),
            title=str(payload["title"]),
            summary=str(payload.get("summary") or ""),
            body=str(payload.get("body") or ""),
            data=dict(payload.get("data") or {}),
            attachments=attachments,
            priority=NotificationPriority(payload.get("priority", NotificationPriority.NORMAL.value)),
            confidence=payload.get("confidence"),
            recipient=payload.get("recipient"),
            open_path=Path(payload["open_path"]) if payload.get("open_path") else None,
        )

    def _already_sent(self, notification_id: str) -> bool:
        return notification_id in self._sent_ledger()

    def _sent_ledger(self) -> set[str]:
        if not self._sent_ledger_path.exists():
            return set()
        try:
            raw = json.loads(self._sent_ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()
        return {str(item) for item in raw if isinstance(item, str)} if isinstance(raw, list) else set()

    def _mark_sent(self, notification_id: str) -> None:
        ledger = self._sent_ledger()
        if notification_id in ledger:
            return
        ledger.add(notification_id)
        self._sent_ledger_path.write_text(json.dumps(sorted(ledger), indent=2), encoding="utf-8")

    def _next_retry_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _notification_id(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _attachment_retry_requested(self, message: NotificationMessage) -> bool:
        return message.category in {NotificationCategory.DAILY_MORNING_BRIEF, NotificationCategory.WEEKLY_STRATEGY_BRIEF, NotificationCategory.MONTHLY_REPORT_BRIEF} and not message.attachments and bool(message.data.get("pending_attachment_path"))

    def _best_item(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "Not available"
        item = values[0]
        if isinstance(item, dict):
            for key in ("title", "summary", "action", "finding", "name", "message", "topic", "hook"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return json.dumps(item, sort_keys=True, default=str)
        return str(item)

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("data", "summary", "title", "message"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()
        return None

    def _float_first(self, payload: dict[str, Any], *keys: str) -> float | None:
        current: Any = payload
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        try:
            return None if current is None else float(current)
        except (TypeError, ValueError):
            return None

    def _log_delivery(self, message: NotificationMessage, outcome: NotificationOutcome) -> None:
        finish = self._logger.measure()
        finish(
            notification_id=message.notification_id,
            category=message.category.value,
            title=message.title,
            delivered=outcome.delivered,
            queued=outcome.queued,
            provider_results=[result.provider for result in outcome.provider_results],
            warnings=list(outcome.warnings),
        )
