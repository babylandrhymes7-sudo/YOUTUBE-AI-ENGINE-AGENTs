"""News collector data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


NewsSourceType = Literal["rss", "reddit", "blog", "website", "store"]


@dataclass(slots=True)
class NewsSourceDefinition:
    """Describe one local news source the engine should collect from."""

    name: str
    source_type: NewsSourceType
    url: str
    category: str | None = None
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    article_link_selector: str | None = None
    article_title_selector: str | None = None
    article_content_selector: str | None = None
    article_image_selector: str | None = None
    article_author_selector: str | None = None
    max_items: int = 25
    headers: dict[str, str] = field(default_factory=dict)
    active: bool = True


@dataclass(slots=True)
class NewsArticle:
    """Normalized article payload used by the news engine."""

    source_name: str
    source_type: NewsSourceType
    source_url: str | None
    source_domain: str | None
    url: str
    title: str
    summary: str | None = None
    full_text: str | None = None
    published_at: datetime | None = None
    category: str | None = None
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    image_url: str | None = None
    author: str | None = None
    language: str | None = None
    raw_payload: dict | None = None