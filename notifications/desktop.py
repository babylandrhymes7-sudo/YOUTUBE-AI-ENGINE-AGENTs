"""macOS desktop notification provider."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .contracts import NotificationChannel, NotificationDeliveryResult, NotificationMessage


class DesktopProvider:
    name = "desktop"
    channel = NotificationChannel.DESKTOP

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        try:
            self._notify(message)
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=True,
                recipient="macos-desktop",
            )
        except Exception as exc:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=self.channel,
                notification_id=message.notification_id,
                success=False,
                error=str(exc),
                recipient="macos-desktop",
            )

    def _notify(self, message: NotificationMessage) -> None:
        subtitle = message.summary.replace('"', '\\"')
        body = message.body.replace('"', '\\"')
        script = f'display notification "{body[:220]}" with title "{message.title}" subtitle "{subtitle[:120]}"'
        subprocess.run(["osascript", "-e", script], check=True)
        if message.open_path:
            path = Path(message.open_path)
            if path.exists():
                subprocess.run(["open", str(path)], check=False)
"""Desktop notification placeholder."""
