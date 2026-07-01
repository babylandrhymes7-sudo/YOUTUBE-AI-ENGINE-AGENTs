"""Versioned prompt loading with no business prompts embedded in Python."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptBundle:
    name: str
    version: str
    system: str
    user: str


class PromptManager:
    """Load replaceable prompt templates from versioned directories."""

    def __init__(self, prompt_root: Path | None = None) -> None:
        self._root = prompt_root or Path(__file__).resolve().parent / "prompts"

    def load(self, name: str, version: str = "v1") -> PromptBundle:
        self._validate_segment(name)
        self._validate_segment(version)
        directory = self._root / name / version
        system_path = directory / "system.md"
        user_path = directory / "user.md"
        if not system_path.is_file() or not user_path.is_file():
            raise FileNotFoundError(f"prompt bundle not found: {name}/{version}")
        return PromptBundle(
            name=name,
            version=version,
            system=system_path.read_text(encoding="utf-8"),
            user=user_path.read_text(encoding="utf-8"),
        )

    def render_user(self, bundle: PromptBundle, context_json: str) -> str:
        marker = "{{KNOWLEDGE_CONTEXT_JSON}}"
        if marker not in bundle.user:
            raise ValueError(f"prompt {bundle.name}/{bundle.version} is missing {marker}")
        return bundle.user.replace(marker, context_json)

    def available_versions(self, name: str) -> list[str]:
        self._validate_segment(name)
        directory = self._root / name
        if not directory.is_dir():
            return []
        return sorted(path.name for path in directory.iterdir() if path.is_dir())

    def _validate_segment(self, value: str) -> None:
        if not value or not all(character.isalnum() or character in {"_", "-"} for character in value):
            raise ValueError(f"invalid prompt path segment: {value!r}")
