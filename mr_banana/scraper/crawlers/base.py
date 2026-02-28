from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from curl_cffi import requests

from mr_banana.utils.network import DEFAULT_USER_AGENT, build_proxies
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
    """Base class for metadata crawlers with shared HTTP/logging infrastructure."""

    name: str

    def __init__(self, cfg: Any = None, log_fn: Callable[[str], None] | None = None):
        self.cfg = cfg
        self._log = log_fn

    # -- Logging --

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    # -- Code extraction --

    def _extract_code(self, file_path: Path) -> str | None:
        return extract_jav_code(file_path)

    # -- Network helpers --

    def _build_proxies(self) -> dict[str, str] | None:
        proxy_url = getattr(self.cfg, "proxy_url", "") if self.cfg else ""
        return build_proxies(proxy_url)

    def _apply_delay(self) -> None:
        delay = getattr(self.cfg, "request_delay_sec", 0.0) if self.cfg else 0.0
        if delay and float(delay) > 0:
            time.sleep(float(delay))

    def _headers(self) -> dict[str, str]:
        """Base headers. Subclasses can override to add cookies, auth, etc."""
        return {"User-Agent": DEFAULT_USER_AGENT}

    def _get_text(self, url: str, *, cookies: dict[str, str] | None = None) -> str | None:
        """GET url, return response text or None on failure."""
        try:
            self._emit(f"GET {url}")
            self._apply_delay()
            r = requests.get(
                url,
                headers=self._headers(),
                cookies=cookies,
                timeout=25,
                verify=False,
                impersonate="chrome",
                proxies=self._build_proxies(),
            )
            self._emit(f"<- {r.status_code} {url}")
            if r.status_code != 200:
                return None
            return r.text
        except Exception as e:
            self._emit(f"!! request error {url}: {e}")
            return None

    def _get_json(self, url: str) -> dict | None:
        """GET url, return parsed JSON dict or None."""
        try:
            self._emit(f"GET {url}")
            self._apply_delay()
            r = requests.get(
                url,
                headers=self._headers(),
                timeout=25,
                verify=False,
                impersonate="chrome",
                proxies=self._build_proxies(),
            )
            self._emit(f"<- {r.status_code} {url}")
            if r.status_code != 200:
                return None
            return r.json()
        except Exception as e:
            self._emit(f"!! request error {url}: {e}")
            return None

    # -- Abstract --

    @abstractmethod
    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        raise NotImplementedError
