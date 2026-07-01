"""News collection engine.

TODO: Keep orchestration limited to collection, duplicate detection, and persistence.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from app.logging import get_logger
from database.models import News
from database.repositories.news import NewsRepository
from sqlalchemy.orm import Session

from .models import NewsArticle, NewsSourceDefinition


logger = get_logger(__name__)


class NewsCollectionEngine:
    """Collect news from RSS, Reddit, blogs, websites, and stores into local PostgreSQL."""

    def __init__(
        self,
        session: Session,
        sources: list[NewsSourceDefinition],
        storage_root: str | Path,
        http_session: requests.Session | None = None,
    ) -> None:
        self.session = session
        self.sources = [source for source in sources if source.active]
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.http_session = http_session or requests.Session()
        self.repository = NewsRepository(session)

    def collect(self) -> dict[str, int]:
        """Collect every configured source and persist the normalized articles locally."""

        stats = {"sources": 0, "articles": 0, "duplicates": 0, "stored_files": 0}
        logger.info("Starting news collection for {} sources", len(self.sources))
        with self.session.begin():
            for source in self.sources:
                stats["sources"] += 1
                collected_articles = self._collect_source(source)
                for article in collected_articles:
                    result = self._store_article(article)
                    stats["articles"] += 1
                    stats["stored_files"] += result["stored_files"]
                    if result["is_duplicate"]:
                        stats["duplicates"] += 1
        logger.info("Completed news collection")
        return stats

    def close(self) -> None:
        """Close the underlying HTTP session."""

        self.http_session.close()

    def _collect_source(self, source: NewsSourceDefinition) -> list[NewsArticle]:
        if source.source_type in {"rss", "reddit"}:
            return self._collect_feed_source(source)
        return self._collect_website_source(source)

    def _collect_feed_source(self, source: NewsSourceDefinition) -> list[NewsArticle]:
        feed = feedparser.parse(source.url)
        articles: list[NewsArticle] = []
        for entry in feed.entries[: source.max_items]:
            article_url = self._get_entry_url(entry, source.url)
            title = self._get_entry_value(entry, ("title",), default=article_url)
            summary = self._get_entry_value(entry, ("summary", "description"))
            published_at = self._parse_datetime(
                self._get_entry_value(entry, ("published_parsed", "updated_parsed"))
            )
            image_url = self._get_entry_image(entry)
            article = self._build_article(
                source,
                article_url,
                title=title,
                summary=summary,
                published_at=published_at,
                image_url=image_url,
                raw_payload=self._entry_to_dict(entry),
            )
            articles.append(article)
        return articles

    def _collect_website_source(self, source: NewsSourceDefinition) -> list[NewsArticle]:
        response = self.http_session.get(source.url, headers=source.headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        article_links = self._extract_article_links(soup, source)
        articles: list[NewsArticle] = []
        for article_url in article_links[: source.max_items]:
            article_response = self.http_session.get(article_url, headers=source.headers, timeout=30)
            article_response.raise_for_status()
            article = self._parse_article_page(source, article_url, article_response.text)
            articles.append(article)
        return articles

    def _parse_article_page(self, source: NewsSourceDefinition, article_url: str, html_text: str) -> NewsArticle:
        soup = BeautifulSoup(html_text, "html.parser")
        title = self._select_text(soup, source.article_title_selector) or self._select_meta(soup, "og:title")
        title = title or self._fallback_title_from_url(article_url)
        summary = self._select_meta(soup, "description")
        if not summary:
            summary = self._select_text(soup, "p")
        full_text = self._extract_main_text(soup, source.article_content_selector)
        image_url = self._select_image(soup, source.article_image_selector, article_url)
        author = self._select_text(soup, source.article_author_selector)
        published_at = self._extract_published_at(soup)
        return self._build_article(
            source,
            article_url,
            title=title,
            summary=summary,
            full_text=full_text,
            published_at=published_at,
            image_url=image_url,
            author=author,
            raw_payload={"html_length": len(html_text)},
            html_text=html_text,
        )

    def _build_article(
        self,
        source: NewsSourceDefinition,
        article_url: str,
        *,
        title: str,
        summary: str | None = None,
        full_text: str | None = None,
        published_at: datetime | None = None,
        image_url: str | None = None,
        author: str | None = None,
        raw_payload: dict | None = None,
        html_text: str | None = None,
    ) -> NewsArticle:
        domain = urlparse(article_url).netloc or urlparse(source.url).netloc or None
        keywords = self._merge_keywords(source.keywords, title, summary, full_text)
        tags = self._build_tags(source, keywords)
        if html_text is not None and full_text is None:
            full_text = self._extract_text_from_html(html_text)
        return NewsArticle(
            source_name=source.name,
            source_type=source.source_type,
            source_url=source.url,
            source_domain=domain,
            url=article_url,
            title=title.strip(),
            summary=summary.strip() if summary else None,
            full_text=full_text.strip() if full_text else None,
            published_at=published_at,
            category=source.category or self._infer_category(source.name, title, summary, full_text),
            keywords=keywords,
            tags=tags,
            image_url=image_url,
            author=author.strip() if author else None,
            raw_payload=raw_payload,
        )

    def _store_article(self, article: NewsArticle) -> dict[str, Any]:
        canonical_url = self._canonicalize_url(article.url)
        content_hash = self._hash_article(article)
        existing_article = self.repository.get_one_by(url=article.url)
        duplicate_of = self._find_duplicate(article.url, canonical_url, content_hash)
        article_folder = self._article_folder(article)
        article_folder.mkdir(parents=True, exist_ok=True)

        article_html_path = self._write_article_html(article_folder, article)
        image_path = self._download_image(article_folder, article.image_url)

        if existing_article is not None:
            record = self.repository.update(
                existing_article,
                source_name=article.source_name,
                source_type=article.source_type,
                source_url=article.source_url,
                source_domain=article.source_domain,
                canonical_url=canonical_url,
                title=article.title,
                summary=article.summary,
                full_text=article.full_text,
                article_html_path=str(article_html_path) if article_html_path else existing_article.article_html_path,
                image_url=article.image_url,
                image_path=str(image_path) if image_path else existing_article.image_path,
                published_at=article.published_at,
                category=article.category,
                keywords=article.keywords,
                tags=article.tags,
                language=article.language,
                author=article.author,
                content_hash=content_hash,
                duplicate_of_id=None,
                duplicate_score=0.0,
                duplicate_reason=None,
                is_duplicate=False,
                raw_payload=article.raw_payload,
            )
            return {
                "record": record,
                "is_duplicate": False,
                "stored_files": int(article_html_path is not None) + int(image_path is not None),
            }

        record = self.repository.create(
            source_name=article.source_name,
            source_type=article.source_type,
            source_url=article.source_url,
            source_domain=article.source_domain,
            url=article.url,
            canonical_url=canonical_url,
            title=article.title,
            summary=article.summary,
            full_text=article.full_text,
            article_html_path=str(article_html_path) if article_html_path else None,
            image_url=article.image_url,
            image_path=str(image_path) if image_path else None,
            published_at=article.published_at,
            category=article.category,
            keywords=article.keywords,
            tags=article.tags,
            language=article.language,
            author=article.author,
            content_hash=content_hash,
            duplicate_of_id=duplicate_of.id if duplicate_of else None,
            duplicate_score=1.0 if duplicate_of else 0.0,
            duplicate_reason="url_match" if duplicate_of and duplicate_of.url == article.url else ("content_hash" if duplicate_of else None),
            is_duplicate=duplicate_of is not None,
            raw_payload=article.raw_payload,
        )
        return {"record": record, "is_duplicate": duplicate_of is not None, "stored_files": int(article_html_path is not None) + int(image_path is not None)}

    def _find_duplicate(self, url: str, canonical_url: str | None, content_hash: str | None) -> News | None:
        duplicate = self.repository.get_one_by(url=url)
        if duplicate is not None:
            return duplicate
        if canonical_url:
            duplicate = self.repository.get_one_by(canonical_url=canonical_url)
            if duplicate is not None:
                return duplicate
        if content_hash:
            duplicate = self.repository.get_one_by(content_hash=content_hash)
        return duplicate

    def _article_folder(self, article: NewsArticle) -> Path:
        published_at = article.published_at or datetime.now(timezone.utc)
        safe_source = self._slugify(article.source_name)
        safe_title = self._slugify(article.title)[:80] or "article"
        return self.storage_root / "news" / safe_source / str(published_at.year) / f"{published_at.month:02d}" / safe_title

    def _write_article_html(self, folder: Path, article: NewsArticle) -> Path | None:
        if not article.full_text:
            return None
        html_path = folder / "article.html"
        html_path.write_text(
            "\n".join(
                [
                    "<html><head><meta charset='utf-8'><title>" + html.escape(article.title) + "</title></head><body>",
                    f"<h1>{html.escape(article.title)}</h1>",
                    f"<p><strong>Source:</strong> {html.escape(article.source_name)}</p>",
                    f"<p><strong>URL:</strong> {html.escape(article.url)}</p>",
                    f"<div>{html.escape(article.full_text).replace(chr(10), '<br>')}</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        return html_path

    def _download_image(self, folder: Path, image_url: str | None) -> Path | None:
        if not image_url:
            return None
        try:
            response = self.http_session.get(image_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return None
        suffix = Path(urlparse(image_url).path).suffix or ".jpg"
        image_path = folder / f"image{suffix}"
        image_path.write_bytes(response.content)
        return image_path

    def _extract_article_links(self, soup: BeautifulSoup, source: NewsSourceDefinition) -> list[str]:
        if source.article_link_selector:
            links = [self._absolute_url(source.url, element.get("href")) for element in soup.select(source.article_link_selector)]
        else:
            links = [
                self._absolute_url(source.url, anchor.get("href"))
                for anchor in soup.find_all("a", href=True)
            ]
        filtered_links = []
        seen_links: set[str] = set()
        source_domain = urlparse(source.url).netloc
        for link in links:
            if not link or link in seen_links:
                continue
            if source_domain and urlparse(link).netloc and urlparse(link).netloc != source_domain and not link.startswith("https://www.reddit.com"):
                continue
            if self._looks_like_navigation_link(link):
                continue
            seen_links.add(link)
            filtered_links.append(link)
        return filtered_links

    def _extract_main_text(self, soup: BeautifulSoup, selector: str | None) -> str | None:
        if selector:
            selected = soup.select_one(selector)
            if selected:
                return self._clean_text(selected.get_text(" ", strip=True))
        article = soup.find("article")
        if article:
            text = self._clean_text(article.get_text(" ", strip=True))
            if text:
                return text
        paragraphs = [self._clean_text(paragraph.get_text(" ", strip=True)) for paragraph in soup.find_all("p")]
        text = " ".join(paragraph for paragraph in paragraphs if paragraph)
        return text or None

    def _extract_published_at(self, soup: BeautifulSoup) -> datetime | None:
        for selector in ("meta[property='article:published_time']", "meta[name='pubdate']", "time[datetime]"):
            element = soup.select_one(selector)
            if not element:
                continue
            value = element.get("content") or element.get("datetime") or element.get_text(strip=True)
            parsed = self._parse_datetime(value)
            if parsed is not None:
                return parsed
        return None

    def _select_text(self, soup: BeautifulSoup, selector: str | None) -> str | None:
        if not selector:
            return None
        element = soup.select_one(selector)
        if element is None:
            return None
        if element.name == "meta":
            return element.get("content")
        return self._clean_text(element.get_text(" ", strip=True))

    def _select_meta(self, soup: BeautifulSoup, property_name: str) -> str | None:
        for selector in (f"meta[property='{property_name}']", f"meta[name='{property_name}']"):
            element = soup.select_one(selector)
            if element and element.get("content"):
                return element.get("content")
        return None

    def _select_image(self, soup: BeautifulSoup, selector: str | None, base_url: str) -> str | None:
        if selector:
            element = soup.select_one(selector)
            if element and element.get("src"):
                return self._absolute_url(base_url, element.get("src"))
        og_image = self._select_meta(soup, "og:image")
        if og_image:
            return self._absolute_url(base_url, og_image)
        image = soup.find("img")
        if image and image.get("src"):
            return self._absolute_url(base_url, image.get("src"))
        return None

    def _get_entry_url(self, entry: Any, fallback_url: str) -> str:
        links = getattr(entry, "links", None) or []
        for link in links:
            if getattr(link, "rel", None) == "alternate" and getattr(link, "href", None):
                return link.href
        return self._get_entry_value(entry, ("link",), default=fallback_url)

    def _get_entry_image(self, entry: Any) -> str | None:
        media_content = getattr(entry, "media_content", None) or []
        for item in media_content:
            if item.get("url"):
                return item["url"]
        media_thumbnail = getattr(entry, "media_thumbnail", None) or []
        for item in media_thumbnail:
            if item.get("url"):
                return item["url"]
        return None

    def _get_entry_value(self, entry: Any, keys: tuple[str, ...], default: str | None = None) -> str | None:
        for key in keys:
            value = getattr(entry, key, None)
            if isinstance(value, list) and value:
                value = value[0]
            if value:
                return self._clean_text(str(value))
        return default

    def _entry_to_dict(self, entry: Any) -> dict[str, Any]:
        return json.loads(json.dumps(getattr(entry, "__dict__", {}), default=str))

    def _hash_article(self, article: NewsArticle) -> str:
        payload = "\n".join(
            [
                article.title.strip().lower(),
                (article.summary or "").strip().lower(),
                (article.full_text or "").strip().lower(),
                self._canonicalize_url(article.url) or article.url,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _canonicalize_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        normalized_path = re.sub(r"/+$", "", parsed.path or "") or "/"
        return parsed._replace(fragment="", query="", path=normalized_path).geturl()

    def _merge_keywords(self, source_keywords: list[str], title: str, summary: str | None, full_text: str | None) -> list[str]:
        text = " ".join(part for part in (title, summary or "", full_text or "") if part)
        lower_text = text.lower()
        keywords: list[str] = []
        for keyword in source_keywords:
            normalized = self._clean_text(keyword).lower()
            if normalized and normalized not in keywords:
                keywords.append(normalized)
        for word in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_+.-]{2,}", lower_text):
            if word not in keywords:
                keywords.append(word)
        return keywords[:40]

    def _build_tags(self, source: NewsSourceDefinition, keywords: list[str]) -> list[str]:
        tags = [self._clean_text(source.source_type).lower(), self._clean_text(source.name).lower()]
        if source.category:
            tags.append(self._clean_text(source.category).lower())
        tags.extend(keywords[:10])
        deduped_tags: list[str] = []
        for tag in tags:
            normalized = self._clean_text(tag).lower()
            if normalized and normalized not in deduped_tags:
                deduped_tags.append(normalized)
        return deduped_tags

    def _infer_category(self, source_name: str, title: str, summary: str | None, full_text: str | None) -> str:
        text = f"{source_name} {title} {summary or ''} {full_text or ''}".lower()
        rules = (
            ("release", "release"),
            ("patch", "patch notes"),
            ("update", "updates"),
            ("review", "reviews"),
            ("sale", "store"),
            ("deal", "store"),
            ("reddit", "community"),
        )
        for needle, category in rules:
            if needle in text:
                return category
        return "news"

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, tuple) and len(value) >= 6:
            return datetime(*value[:6], tzinfo=timezone.utc)
        if hasattr(value, "tm_year"):
            return datetime(value.tm_year, value.tm_mon, value.tm_mday, value.tm_hour, value.tm_min, value.tm_sec, tzinfo=timezone.utc)
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _absolute_url(self, base_url: str, url: str | None) -> str | None:
        if not url:
            return None
        return urljoin(base_url, url)

    def _fallback_title_from_url(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        tail = path.split("/")[-1] if path else url
        return tail.replace("-", " ").replace("_", " ").title() or url

    def _looks_like_navigation_link(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        navigation_fragments = ("/tag/", "/category/", "/author/", "/feed", "/wp-content/", "/privacy", "/terms")
        return any(fragment in path for fragment in navigation_fragments)

    def _clean_text(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _extract_text_from_html(self, html_text: str) -> str | None:
        soup = BeautifulSoup(html_text, "html.parser")
        return self._extract_main_text(soup, None)

    def _slugify(self, value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-") or "source"