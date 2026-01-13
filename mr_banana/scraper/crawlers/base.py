from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..types import CrawlResult, MediaInfo


class BaseCrawler(ABC):
    name: str

    @abstractmethod
    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        raise NotImplementedError
