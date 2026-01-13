from __future__ import annotations

import re
from pathlib import Path

from mr_banana.extractors.jable import JableExtractor
from mr_banana.utils.network import NetworkHandler

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler


class HistoryJableCrawler(BaseCrawler):
    """Fetch metadata from jable.tv by reusing the original URL stored in Mr. Banana download history.

    This keeps the "site crawling" scoped to Mr. Banana's supported website.
    """

    name = "jable"

    def __init__(self, history_lookup):
        self._history_lookup = history_lookup
        self._extractor = JableExtractor(NetworkHandler())

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        url = self._history_lookup(str(file_path))
        if not url:
            return None

        info = self._extractor.extract(url)
        if not info:
            return None

        return CrawlResult(
            source=self.name,
            title=info.get("title"),
            external_id=info.get("id"),
            original_url=url,
            data=info.get("metadata") or {},
        )
