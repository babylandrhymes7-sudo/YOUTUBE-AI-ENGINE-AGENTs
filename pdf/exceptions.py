"""Custom exceptions for PDF generation."""

from __future__ import annotations


class PDFEngineError(RuntimeError):
    """Base class for PDF engine failures."""


class InvalidReportJSONError(PDFEngineError):
    """Raised when report JSON is malformed or missing required fields."""


class MissingDirectoryError(PDFEngineError):
    """Raised when the output directory cannot be created or accessed."""


class DiskWriteError(PDFEngineError):
    """Raised when the PDF cannot be written to disk."""


class RenderFailureError(PDFEngineError):
    """Raised when ReportLab fails while rendering the document."""


class MissingImageError(PDFEngineError):
    """Raised when an expected image path does not exist."""


class MissingChartError(PDFEngineError):
    """Raised when an expected chart image is unavailable."""


class InvalidFontError(PDFEngineError):
    """Raised when a configured font cannot be loaded."""
