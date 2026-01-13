from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MediaInfo:
    path: Path
    size_bytes: int | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class CrawlResult:
    """Normalized metadata produced by crawlers.

    Keep this intentionally minimal; we can extend later.
    """

    source: str
    title: str | None = None
    external_id: str | None = None
    original_url: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrapeItemResult:
    path: Path
    media: MediaInfo
    merged: CrawlResult
    sources: list[CrawlResult] = field(default_factory=list)
    subtitles: list[Path] = field(default_factory=list)
