from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from curl_cffi import requests

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler


@dataclass
class ThePornDBConfig:
    api_token: str = ""
    request_delay_sec: float = 0.0
    proxy_url: str = ""  # optional


class ThePornDBCrawler(BaseCrawler):
    """Scrape plot/metadata from ThePornDB API (requires API token).

    This is best-effort: if no token is configured, the crawler returns None.
    """

    name = "theporndb"

    def __init__(self, cfg: ThePornDBConfig | None = None, log_fn=None):
        self.cfg = cfg or ThePornDBConfig()
        self._log = log_fn

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    def _extract_code(self, file_path: Path) -> str | None:
        stem = file_path.stem.strip()
        if not stem:
            return None
        # Exact match: waaa-585 / ssis-001
        if re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9]+", stem):
            return stem
        # Extract code from filename with extra content
        # Match common JAV code patterns: 2-6 letters + hyphen + 2-5 digits
        match = re.search(r"(?<![A-Za-z])([A-Za-z]{2,6})-(\d{2,5})(?![A-Za-z0-9-])", stem, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()}-{match.group(2)}"
        # Also support patterns without hyphen like "ABC123" -> "ABC-123"
        match = re.search(r"(?<![A-Za-z])([A-Za-z]{2,6})(\d{2,5})(?![A-Za-z0-9])", stem, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()}-{match.group(2)}"
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.api_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

    def _get_json(self, url: str) -> dict | None:
        try:
            self._emit(f"GET {url}")
            if self.cfg.request_delay_sec and self.cfg.request_delay_sec > 0:
                import time

                time.sleep(float(self.cfg.request_delay_sec))

            proxies = None
            if getattr(self.cfg, "proxy_url", ""):
                pu = str(self.cfg.proxy_url).strip()
                if pu:
                    proxies = {"http": pu, "https": pu}

            r = requests.get(
                url,
                headers=self._headers(),
                timeout=25,
                verify=False,
                impersonate="chrome",
                proxies=proxies,
            )
            self._emit(f"<- {r.status_code} {url}")
            if r.status_code != 200:
                return None
            return r.json()
        except Exception as e:
            self._emit(f"!! request error {url}: {e}")
            return None

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        code = self._extract_code(file_path)
        if not code:
            return None

        token = str(getattr(self.cfg, "api_token", "") or "").strip()
        if not token:
            self._emit("skip theporndb: missing api token")
            return None

        # Search scenes first; keep results small.
        q = quote_plus(code)
        search_url = f"https://api.theporndb.net/scenes?q={q}&per_page=10"
        payload = self._get_json(search_url)
        if not payload:
            return None

        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            return None

        def norm(s: str) -> str:
            return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())

        want = norm(code)
        picked = None
        for it in items:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "")
            if want and want in norm(title):
                picked = it
                break
        picked = picked or items[0]
        if not isinstance(picked, dict):
            return None

        title = str(picked.get("title") or "")
        plot = str(picked.get("description") or picked.get("synopsis") or "").strip()
        release = str(picked.get("date") or picked.get("release_date") or "").strip()

        # lightweight artwork fields (not all are guaranteed)
        poster_url = str(picked.get("poster") or picked.get("poster_url") or "").strip()
        fanart_url = str(picked.get("background") or picked.get("background_url") or "").strip()

        original_url = ""
        slug = picked.get("slug")
        if slug:
            original_url = f"https://theporndb.net/scenes/{slug}"

        data = {
            "number": code,
            "plot": plot,
            "release": release,
            "poster_url": poster_url,
            "fanart_url": fanart_url,
        }

        return CrawlResult(
            source=self.name,
            title=title or code,
            external_id=code,
            original_url=original_url or None,
            data=data,
        )
