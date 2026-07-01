"""Telegram Bot notification provider."""

from __future__ import annotations

from pathlib import Path

import requests

from app.config import settings

from .contracts import NotificationAttachment, NotificationChannel, NotificationDeliveryResult, NotificationMessage


class TelegramProvider:
    name = "telegram"
    channel = NotificationChannel.TELEGRAM

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None, base_url: str = "https://api.telegram.org") -> None:
        self._bot_token = bot_token or settings.telegram_bot_token
        self._chat_id = chat_id or settings.telegram_chat_id
        self._base_url = base_url.rstrip("/")

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        if not self._bot_token or not self._chat_id:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=False,
                error="telegram bot token or chat id is not configured",
                recipient=self._chat_id or None,
            )
        try:
            self._post_message(message.title, message.body)
            attachment_sent = False
            for attachment in message.attachments:
                attachment_sent = self._send_attachment(attachment) or attachment_sent
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=True,
                attachment_sent=attachment_sent,
                recipient=self._chat_id,
            )
        except Exception as exc:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=False,
                error=str(exc),
                recipient=self._chat_id,
            )

    def _post_message(self, title: str, body: str) -> None:
        url = f"{self._base_url}/bot{self._bot_token}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": self._chat_id, "text": f"*{title}*\n\n{body}", "parse_mode": "Markdown"},
            timeout=30,
        )
        response.raise_for_status()

    def _send_attachment(self, attachment: NotificationAttachment) -> bool:
        path = Path(attachment.path)
        if not path.exists():
            return False
        endpoint = "sendDocument"
        if attachment.mime_type.startswith("image/") or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            endpoint = "sendPhoto"
        url = f"{self._base_url}/bot{self._bot_token}/{endpoint}"
        with path.open("rb") as file_handle:
            field_name = "document" if endpoint == "sendDocument" else "photo"
            response = requests.post(
                url,
                data={"chat_id": self._chat_id},
                files={field_name: (attachment.filename or path.name, file_handle, attachment.mime_type)},
                timeout=60,
            )
        response.raise_for_status()
        return True
"""Telegram notification placeholder."""
