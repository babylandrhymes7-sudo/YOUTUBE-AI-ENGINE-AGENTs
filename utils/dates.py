"""Date helpers.

TODO: Keep date and timestamp parsing reusable across collectors and services.
"""

from __future__ import annotations

from datetime import datetime, timezone


def parse_iso_datetime(value: str | None) -> datetime | None:
	"""Parse an ISO 8601 datetime string into a timezone-aware datetime."""

	if not value:
		return None
	normalized = value.replace("Z", "+00:00")
	parsed = datetime.fromisoformat(normalized)
	if parsed.tzinfo is None:
		return parsed.replace(tzinfo=timezone.utc)
	return parsed

