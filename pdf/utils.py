"""Utility helpers for the PDF engine."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .exceptions import MissingDirectoryError


REPORT_NAME_MAP = {
    "daily": "Daily_Report",
    "weekly": "Weekly_Report",
    "monthly": "Monthly_Report",
    "comparison": "Comparison_Report",
    "historical": "Historical_Report",
    "executive": "Executive_Report",
}


def ensure_directory(path: Path) -> None:
    """Create a directory tree if needed."""

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MissingDirectoryError(f"Unable to create directory: {path}") from exc


def sanitize_filename(value: str) -> str:
    """Return a filesystem-safe filename segment."""

    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_") or "Report"


def build_report_basename(report_type: str, generated_at: datetime) -> str:
    """Build report filename base without extension."""

    prefix = REPORT_NAME_MAP.get(report_type.lower(), "Custom_Report")
    return f"{prefix}_{generated_at:%Y_%m_%d}"


def resolve_output_path(
    output_dir: Path,
    report_type: str,
    generated_at: datetime,
    *,
    overwrite: bool = False,
) -> Path:
    """Return a non-colliding local file path for the generated PDF."""

    ensure_directory(output_dir)
    basename = sanitize_filename(build_report_basename(report_type, generated_at))
    candidate = output_dir / f"{basename}.pdf"
    if overwrite or not candidate.exists():
        return candidate

    version = 2
    while True:
        candidate = output_dir / f"{basename}_v{version}.pdf"
        if not candidate.exists():
            return candidate
        version += 1


def archive_previous_reports(output_dir: Path, report_type: str, generated_at: datetime) -> None:
    """Archive prior PDFs of the same report type into storage/reports/archive."""

    ensure_directory(output_dir)
    prefix = REPORT_NAME_MAP.get(report_type.lower(), "Custom_Report")
    archive_dir = output_dir / "archive" / generated_at.strftime("%Y_%m")
    ensure_directory(archive_dir)

    for file_path in output_dir.glob(f"{prefix}_*.pdf"):
        if not file_path.is_file():
            continue
        target = archive_dir / file_path.name
        suffix = 2
        while target.exists():
            target = archive_dir / f"{file_path.stem}_a{suffix}.pdf"
            suffix += 1
        try:
            file_path.replace(target)
        except OSError:
            # Archiving is best-effort; generation still proceeds with versioned filenames.
            continue
