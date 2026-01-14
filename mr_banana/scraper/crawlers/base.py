from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from ..types import CrawlResult, MediaInfo


def extract_jav_code(file_path: Path) -> str | None:
    """
    Extract JAV code from filename, handling various formats:
    - ADN-529, WAAA-585, SSIS-001 (standard)
    - ADN-529-C, ADN-748ch (with suffix)
    - 4k2.me@adn-757ch (with prefix)
    - adn529, ADN529 (no hyphen)
    
    Returns normalized code like "ADN-529" or None if not found.
    """
    stem = file_path.stem.strip()
    if not stem:
        return None
    
    # Clean up common prefixes like "4k2.me@", "xxx@", etc.
    stem = re.sub(r'^[A-Za-z0-9._-]*@', '', stem)
    
    # Pattern: 2-6 letters + hyphen + 2-5 digits (ignore suffix like -C, ch, etc.)
    # Examples: ADN-529-C -> ADN-529, ADN-748ch -> ADN-748
    match = re.search(r'(?<![A-Za-z])([A-Za-z]{2,6})-(\d{2,5})(?=[^0-9]|$)', stem, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    
    # Pattern without hyphen: ABC123, adn529 -> ADN-529
    match = re.search(r'(?<![A-Za-z])([A-Za-z]{2,6})(\d{2,5})(?=[^0-9]|$)', stem, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    
    return None


class BaseCrawler(ABC):
    name: str

    @abstractmethod
    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        raise NotImplementedError
