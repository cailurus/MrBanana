from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler


@dataclass
class JavtrailersConfig:
    base_url: str = "https://javtrailers.com"
    # The public API used by javtrailers.com requires an Authorization header.
    # This value is sourced from an open-source integration and may change.
    auth_token: str = "AELAbPQCh_fifd93wMvf_kxMD_fqkUAVf@BVgb2!md@TNW8bUEopFExyGCoKRcZX"
    request_delay_sec: float = 0.0
    proxy_url: str = ""  # optional


class JavtrailersCrawler(BaseCrawler):
    """Scrape metadata from javtrailers.com via its JSON API.

    Note:
    - javtrailers.com is protected by anti-bot measures. This crawler is best-effort.
    - We use curl_cffi with browser impersonation and a stable Authorization header.
    """

    name = "javtrailers"

    def __init__(self, cfg: JavtrailersConfig | None = None, log_fn=None):
        self.cfg = cfg or JavtrailersConfig()
        self._log = log_fn

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    def _headers(self) -> dict[str, str]:
        h = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
        }
        token = str(getattr(self.cfg, "auth_token", "") or "").strip()
        if token:
            h["Authorization"] = token
        return h

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

    def _to_content_id(self, code: str) -> str | None:
        # Example: WAAA-585 -> waaa00585
        m = re.fullmatch(r"([A-Za-z]+)-(\d{1,6})", (code or "").strip())
        if not m:
            return None
        prefix = m.group(1).lower()
        num = m.group(2).zfill(5)
        return f"{prefix}{num}"

    def _is_cf_challenge_html(self, text: str) -> bool:
        low = (text or "").lower()
        return ("just a moment" in low and "cloudflare" in low) or "cdn-cgi/challenge" in low

    def _hd_gallery(self, urls: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for u in urls or []:
            s = str(u or "").strip()
            if not s:
                continue
            if s.startswith("https://pics.dmm.co.jp/") or s.startswith("http://pics.dmm.co.jp/"):
                # javtrailers sometimes returns ...-01.jpg, but the HD variant is ...jp-01.jpg
                s = re.sub(r"-(\d+)\.jpg$", r"jp-\1.jpg", s, flags=re.IGNORECASE)
            elif s.startswith("https://image.mgstage.com/"):
                s = s.replace("cap_t1_", "cap_e_")
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def _derive_dmm_artwork(self, cover_url: str) -> tuple[str | None, str | None]:
        """Derive DMM artwork variants.

        DMM commonly exposes:
        - poster (portrait): ...ps.jpg
        - fanart (landscape): ...pl.jpg
        """
        u = str(cover_url or "").strip()
        if not u:
            return None, None
        low = u.lower()
        if "pics.dmm.co.jp/" not in low:
            return None, None

        # Only switch the final "ps.jpg" / "pl.jpg" suffix.
        if re.search(r"(?i)ps\.jpg(?=$|\?)", u):
            poster = u
            fanart = re.sub(r"(?i)ps\.jpg(?=$|\?)", "pl.jpg", u, count=1)
            return poster, fanart
        if re.search(r"(?i)pl\.jpg(?=$|\?)", u):
            fanart = u
            poster = re.sub(r"(?i)pl\.jpg(?=$|\?)", "ps.jpg", u, count=1)
            return poster, fanart
        return None, None

    def _fetch_video_api(self, content_id: str, proxies: dict | None) -> dict | None:
        """Fetch video data from javtrailers API. Returns parsed JSON or None."""
        api_url = f"{self.cfg.base_url}/api/video/{content_id}"
        self._emit(f"GET {api_url}")
        try:
            r = requests.get(
                api_url,
                headers=self._headers(),
                timeout=25,
                verify=False,
                impersonate="chrome",
                proxies=proxies,
            )
        except Exception as e:
            self._emit(f"!! request error {api_url}: {e}")
            return None

        self._emit(f"<- {r.status_code} {api_url}")
        if r.status_code != 200:
            return None

        raw_text = getattr(r, "text", None) or ""
        if self._is_cf_challenge_html(raw_text):
            self._emit("blocked: Cloudflare challenge page")
            return None

        try:
            payload = json.loads(raw_text)
            if isinstance(payload, dict) and isinstance(payload.get("video"), dict):
                return payload
        except Exception:
            pass
        return None

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        code = self._extract_code(file_path)
        if not code:
            return None

        content_id = self._to_content_id(code)
        if not content_id:
            return None

        if self.cfg.request_delay_sec and self.cfg.request_delay_sec > 0:
            time.sleep(float(self.cfg.request_delay_sec))

        proxies = None
        if getattr(self.cfg, "proxy_url", ""):
            pu = str(self.cfg.proxy_url).strip()
            if pu:
                proxies = {"http": pu, "https": pu}

        # Try without prefix first, then with "1" prefix (DMM convention for some videos)
        payload = self._fetch_video_api(content_id, proxies)
        used_content_id = content_id
        if payload is None:
            # Try with "1" prefix - common for DMM digital exclusive content
            alt_content_id = f"1{content_id}"
            payload = self._fetch_video_api(alt_content_id, proxies)
            if payload is not None:
                used_content_id = alt_content_id

        if payload is None:
            return None

        video = payload.get("video") if isinstance(payload, dict) else None
        if not isinstance(video, dict):
            return None

        # Ensure upstream metadata is Japanese-first.
        # JavTrailers sometimes includes zh/English fields; we intentionally prefer jp*.
        title = str(video.get("jpTitle") or video.get("title") or "").strip() or None
        dvd_id = str(video.get("dvdId") or "").strip() or code

        casts = video.get("casts")
        actors: list[str] = []
        if isinstance(casts, list):
            for c in casts:
                if not isinstance(c, dict):
                    continue
                name = str(c.get("name") or "").strip()
                jp = str(c.get("jpName") or "").strip()
                t = jp or name
                if t and t not in actors:
                    actors.append(t)

        categories = video.get("categories")
        tags: list[str] = []
        if isinstance(categories, list):
            for cat in categories:
                if not isinstance(cat, dict):
                    continue
                t = str(cat.get("jpName") or cat.get("name") or "").strip()
                if t and t not in tags:
                    tags.append(t)

        studio = ""
        st = video.get("studio")
        if isinstance(st, dict):
            studio = str(st.get("jpName") or st.get("name") or "").strip()

        release = str(video.get("releaseDate") or "").strip()
        # Normalize ISO date format (e.g., 2025-11-21T03:00:00.000Z) to simple date (2025-11-21)
        if release and "T" in release:
            release = release.split("T")[0]

        duration = video.get("duration")
        runtime = ""
        try:
            if isinstance(duration, (int, float)) and int(duration) > 0:
                runtime = str(int(duration))
        except Exception:
            runtime = ""

        cover = str(video.get("image") or "").strip()
        if cover.startswith("//"):
            cover = "https:" + cover

        trailer = str(video.get("trailer") or "").strip()
        if trailer.startswith("//"):
            trailer = "https:" + trailer

        gallery = video.get("gallery")
        preview_urls: list[str] = []
        if isinstance(gallery, list):
            preview_urls = self._hd_gallery([str(x) for x in gallery])

        out = CrawlResult(source=self.name)
        out.title = title
        out.external_id = dvd_id
        out.original_url = f"{self.cfg.base_url}/video/{used_content_id}"

        if studio:
            out.data["studio"] = studio
            out.data["publisher"] = studio

        if release:
            out.data["release"] = release

        if runtime:
            out.data["runtime"] = runtime

        if actors:
            out.data["actors"] = actors

        if tags:
            out.data["tags"] = tags

        if cover:
            out.data["cover_url"] = cover

            poster, fanart = self._derive_dmm_artwork(cover)
            if poster:
                out.data["poster_url"] = poster
            if fanart:
                out.data["fanart_url"] = fanart

        if preview_urls:
            out.data["preview_urls"] = preview_urls

        if trailer and (trailer.startswith("http://") or trailer.startswith("https://")):
            out.data["trailer_url"] = trailer

        # Also expose the exact javtrailers content id for debugging.
        out.data["javtrailers_content_id"] = used_content_id

        return out
