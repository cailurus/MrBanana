from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from mr_banana.utils.network import DEFAULT_USER_AGENT
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
        super().__init__(cfg=cfg or ThePornDBConfig(), log_fn=log_fn)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.api_token}",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

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
