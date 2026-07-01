"""SMTP email notification provider."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.config import settings

from .contracts import NotificationAttachment, NotificationChannel, NotificationDeliveryResult, NotificationMessage


class EmailProvider:
    name = "email"
    channel = NotificationChannel.EMAIL

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        sender: str | None = None,
        recipients: list[str] | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
    ) -> None:
        self._smtp_host = smtp_host or settings.smtp_host
        self._smtp_port = smtp_port or settings.smtp_port
        self._sender = sender or settings.email_sender
        configured_recipients = recipients if recipients is not None else [item.strip() for item in settings.email_recipients.split(",") if item.strip()]
        self._recipients = configured_recipients
        self._username = username or settings.smtp_username or None
        self._password = password or settings.smtp_password or None
        self._use_tls = settings.smtp_use_tls if use_tls is None else use_tls

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        if not self._recipients:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=False,
                error="email recipients are not configured",
            )
        email = EmailMessage()
        email["Subject"] = message.title
        email["From"] = self._sender
        email["To"] = ", ".join(self._recipients)
        email.set_content(f"{message.summary}\n\n{message.body}")
        for attachment in message.attachments:
            self._attach(email, attachment)
        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=60) as client:
                if self._use_tls:
                    client.starttls()
                if self._username and self._password:
                    client.login(self._username, self._password)
                client.send_message(email)
        except Exception as exc:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=False,
                error=str(exc),
                recipient=", ".join(self._recipients),
            )
        return NotificationDeliveryResult(
            provider=self.name,
            channel=self.channel,
            notification_id=message.notification_id,
            success=True,
            attachment_sent=bool(message.attachments),
            recipient=", ".join(self._recipients),
        )

    def _attach(self, email: EmailMessage, attachment: NotificationAttachment) -> None:
        path = Path(attachment.path)
        if not path.exists():
            return
        maintype, subtype = (attachment.mime_type or "application/octet-stream").split("/", 1)
        email.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.filename or path.name)
"""Email notification placeholder."""
