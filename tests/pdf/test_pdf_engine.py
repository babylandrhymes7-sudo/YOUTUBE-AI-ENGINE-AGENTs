"""Unit tests for the local ReportLab PDF Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pdf import InvalidReportJSONError, PDFEngine


def _base_report() -> dict:
    return {
        "report_type": "daily",
        "title": "Executive Daily Report",
        "generated_at": datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc).isoformat(),
        "version": 1,
        "metadata": {
            "author": "Lead Analyst",
            "generator": "YOUTUBE AI AGENT PDF Engine",
        },
        "executive_summary": {
            "status": "available",
            "data": "Channel performance improved week over week.",
            "warnings": [],
        },
        "action_plan": {
            "status": "available",
            "data": [
                {"priority": "high", "action": "Publish more shorts", "owner": "content"},
                {"priority": "medium", "action": "Refresh thumbnails", "owner": "design"},
            ],
            "warnings": [],
        },
    }


def test_pdf_generation_creates_file(tmp_path: Path) -> None:
    engine = PDFEngine(output_dir=tmp_path)
    result = engine.generate(_base_report())

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".pdf"
    assert 1 <= result.pages_generated <= 8


def test_pdf_generation_large_report(tmp_path: Path) -> None:
    report = _base_report()
    report["report_type"] = "weekly"
    report["historical_table"] = {
        "status": "available",
        "data": [
            {"day": idx, "views": idx * 13, "ctr": round((idx % 10) / 10, 2), "retention": 30 + (idx % 50)}
            for idx in range(1, 2200)
        ],
        "warnings": [],
    }
    engine = PDFEngine(output_dir=tmp_path)

    result = engine.generate(report)

    assert result.output_path.exists()
    assert 1 <= result.pages_generated <= 15
    assert result.tables_rendered >= 1


def test_pdf_generation_handles_missing_images_and_charts(tmp_path: Path) -> None:
    report = _base_report()
    report["assets"] = {
        "status": "available",
        "data": {
            "image_path": str(tmp_path / "missing_logo.png"),
            "chart": {
                "chart_path": str(tmp_path / "missing_chart.png"),
                "caption": "CTR trend",
            },
        },
        "warnings": [],
    }
    engine = PDFEngine(output_dir=tmp_path)

    result = engine.generate(report)

    assert result.output_path.exists()
    assert len(result.warnings) >= 1


def test_pdf_generation_empty_report_rejected(tmp_path: Path) -> None:
    engine = PDFEngine(output_dir=tmp_path)

    with pytest.raises(InvalidReportJSONError):
        engine.generate({})


def test_pdf_versioning_does_not_overwrite(tmp_path: Path) -> None:
    engine = PDFEngine(output_dir=tmp_path)

    first = engine.generate(_base_report())
    second = engine.generate(_base_report())

    assert first.output_path == second.output_path
    archive_dir = tmp_path / "archive" / "2026_07"
    assert archive_dir.exists()
    archived_files = list(archive_dir.glob("Daily_Report_2026_07_01*.pdf"))
    assert archived_files


def test_pdf_metadata_embedded(tmp_path: Path) -> None:
    engine = PDFEngine(output_dir=tmp_path)

    result = engine.generate(_base_report())
    payload = result.output_path.read_bytes()

    assert b"/Title (Executive Daily Report)" in payload
    assert b"/Author (Lead Analyst)" in payload
    assert b"/Creator (YOUTUBE AI AGENT PDF Engine)" in payload


def test_pdf_overwrite_allowed(tmp_path: Path) -> None:
    engine = PDFEngine(output_dir=tmp_path)

    first = engine.generate(_base_report())
    second = engine.generate(_base_report(), overwrite=True)

    assert first.output_path == second.output_path


def test_monthly_page_limit_is_enforced(tmp_path: Path) -> None:
    report = _base_report()
    report["report_type"] = "monthly"
    report["bulk"] = {
        "status": "available",
        "data": [{"index": idx, "metric": idx * 2} for idx in range(5000)],
        "warnings": [],
    }

    engine = PDFEngine(output_dir=tmp_path)
    result = engine.generate(report)

    assert 1 <= result.pages_generated <= 20


def test_pdf_file_creation_in_nested_folder(tmp_path: Path) -> None:
    output_dir = tmp_path / "storage" / "reports"
    engine = PDFEngine(output_dir=output_dir)

    result = engine.generate(_base_report())

    assert output_dir.exists()
    assert result.output_path.exists()
