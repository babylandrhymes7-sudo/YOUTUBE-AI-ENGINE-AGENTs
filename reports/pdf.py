"""Compatibility adapter for PDF export.

TODO: Keep old reports.* imports working while the dedicated pdf package is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf import PDFEngine, PDFEngineResult


class ReportPDFExporter:
	"""Thin wrapper that delegates report rendering to the dedicated PDFEngine."""

	def __init__(self, output_dir: str | Path = Path("storage") / "reports") -> None:
		self._engine = PDFEngine(output_dir=output_dir)

	def export(self, report_json: dict[str, Any], *, overwrite: bool = False) -> PDFEngineResult:
		"""Generate a local PDF from an already validated report JSON payload."""

		return self._engine.generate(report_json, overwrite=overwrite)
