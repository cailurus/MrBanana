from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from curl_cffi import requests

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler, extract_jav_code


@dataclass
class JavdbConfig:
    base_url: str = "https://javdb.com"
    cookie: str = ""  # optional
    request_delay_sec: float = 0.0
    proxy_url: str = ""  # optional


class JavdbCrawler(BaseCrawler):
    """Scrape metadata from JavDB (non-Jable upstream source).

    This is intentionally lightweight: search by code -> open detail page -> extract common fields.
    """

    name = "javdb"

    def __init__(self, cfg: JavdbConfig | None = None, log_fn=None):
        self.cfg = cfg or JavdbConfig()
        self._log = log_fn

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
        }
        if self.cfg.cookie:
            headers["Cookie"] = self.cfg.cookie
        return headers

    def _get_text(self, url: str) -> str | None:
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
            return r.text
        except Exception as e:
            self._emit(f"!! request error {url}: {e}")
            return None

    def _extract_code(self, file_path: Path) -> str | None:
        return extract_jav_code(file_path)

    def _find_first_detail_url(self, html: str, code: str) -> str | None:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            boxes = soup.select("a.box")
            if not boxes:
                return None

            def norm(s: str) -> str:
                return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())

            want = norm(code)

            # Prefer exact code match from the result card's UID (more reliable than title contains).
            for a in boxes:
                uid_el = a.select_one(".uid")
                uid_txt = uid_el.get_text(" ", strip=True) if uid_el else ""
                if uid_txt and want and norm(uid_txt) == want:
                    href = a.get("href")
                    if href:
                        return urljoin(self.cfg.base_url, href)

            # Fallback: accept a title that contains the code.
            for a in boxes:
                title = (a.get_text(" ", strip=True) or "")
                if want and want in norm(title):
                    href = a.get("href")
                    if href:
                        return urljoin(self.cfg.base_url, href)

            href = boxes[0].get("href")
            return urljoin(self.cfg.base_url, href) if href else None
        except Exception:
            return None

    def _text_after_label(self, soup, labels: list[str]) -> str:
        for lab in labels:
            node = soup.find("strong", string=lambda s: isinstance(s, str) and lab in s)
            if not node:
                continue
            parent = node.parent
            if not parent:
                continue
            # common structure: <strong>xxx</strong> <span>...</span>
            span = parent.find("span")
            if span:
                return span.get_text(" ", strip=True)
            # fallback to parent text
            text = parent.get_text(" ", strip=True)
            if text:
                return text
        return ""

    def _links_after_label(self, soup, labels: list[str]) -> list[str]:
        for lab in labels:
            node = soup.find("strong", string=lambda s: isinstance(s, str) and lab in s)
            if not node:
                continue
            parent = node.parent
            if not parent:
                continue
            span = parent.find("span")
            scope = span or parent
            links = [a.get_text(" ", strip=True) for a in scope.find_all("a")]
            links = [x for x in links if x]
            if links:
                # stable de-dup
                return list(dict.fromkeys(links))
        return []

    def _parse_detail(self, detail_url: str, html: str, code: str) -> CrawlResult | None:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")

        def pick_text(sel: str) -> str:
            el = soup.select_one(sel)
            return el.get_text(" ", strip=True) if el else ""

        title = pick_text("h2.title strong.current-title") or pick_text("h2.title")
        originaltitle = pick_text("h2.title span.origin-title")

        # Validate that the detail page matches the requested code.
        # JavDB search sometimes returns near matches; do not accept mismatched pages.
        def _norm_code(s: str) -> str:
            return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())

        want = _norm_code(code)
        page_code = ""
        try:
            raw_id = self._text_after_label(soup, ["識別碼:", "识别码:", "ID:", "品番:", "番号:", "番號:"])
            if raw_id:
                m = re.search(r"[A-Za-z0-9]+-[A-Za-z0-9]+", raw_id)
                page_code = m.group(0) if m else raw_id
        except Exception:
            page_code = ""
        if page_code and want and _norm_code(page_code) != want:
            self._emit(f"skip detail: id mismatch want={code} got={page_code}")
            return None

        # cover
        cover_url = ""
        cover_el = soup.select_one("img.video-cover")
        if cover_el and cover_el.get("src"):
            cover_url = urljoin(self.cfg.base_url, cover_el.get("src"))

        # actors/tags
        actors = self._links_after_label(soup, ["演員:", "演员:", "Actors:"])
        tags = self._links_after_label(soup, ["類別:", "类别:", "Tags:"])

        # studio/publisher/series/release/runtime/directors
        studio = ""
        publisher = ""
        series = ""
        release = ""
        runtime = ""
        directors = []

        studio = self._links_after_label(soup, ["片商:", "Maker:"])
        studio = studio[0] if studio else ""
        publisher = self._links_after_label(soup, ["發行:", "发行:", "Publisher:"])
        publisher = publisher[0] if publisher else ""
        series = self._links_after_label(soup, ["系列:", "Series:"])
        series = series[0] if series else ""
        release = self._text_after_label(soup, ["日期:", "Released Date:"]).strip()
        runtime = self._text_after_label(soup, ["時長", "时长", "Duration:"])
        directors = self._links_after_label(soup, ["導演:", "导演:", "Director:"])

        # rating (best effort; DOM varies by locale)
        rating = ""
        try:
            for sel in [
                ".rating",
                ".score",
                ".score .value",
                "span.rating",
                "span.score",
            ]:
                el = soup.select_one(sel)
                if not el:
                    continue
                txt = el.get_text(" ", strip=True)
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", txt)
                if m:
                    rating = m.group(1)
                    break
        except Exception:
            rating = ""

        # normalize release to yyyy-mm-dd if possible
        release_norm = ""
        if release:
            m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", release)
            if m:
                y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
                release_norm = f"{y}-{mo}-{d}"
        release_norm = release_norm or release

        # runtime minutes
        runtime_min = ""
        if runtime:
            m = re.search(r"(\d+)", runtime)
            runtime_min = m.group(1) if m else ""

        # preview images
        preview_urls: list[str] = []
        for a in soup.select("div.preview-images a.tile-item"):
            href = a.get("href")
            if not href:
                continue
            preview_urls.append(urljoin(self.cfg.base_url, href))
        preview_urls = list(dict.fromkeys(preview_urls))

        # trailer
        trailer_url = ""
        src = soup.select_one("video#preview-video source")
        if src and src.get("src"):
            trailer_url = src.get("src")
            if trailer_url.startswith("//"):
                trailer_url = "https:" + trailer_url
            else:
                trailer_url = urljoin(self.cfg.base_url, trailer_url)

        # poster url (often derivable from cover)
        poster_url = ""
        if cover_url and "/covers/" in cover_url:
            poster_url = cover_url.replace("/covers/", "/thumbs/")

        def _looks_generic_site_desc(s: str) -> bool:
            t = (s or "").strip()
            if not t:
                return True
            # JavDB's generic site tagline sometimes appears as meta description.
            # Example: "番号搜磁链，管理你的成人影片并分享你的想法"
            bad_markers = [
                "番号搜磁链",
                "管理你的成人影片",
                "分享你的想法",
            ]
            if any(m in t for m in bad_markers):
                return True
            # Very short descriptions are rarely real plot.
            if len(t) < 30:
                return True
            return False

        # plot / description (best effort)
        plot = ""
        for lab in ["簡介", "简介", "Description", "Storyline", "剧情", "劇情"]:
            node = soup.find("strong", string=lambda s: isinstance(s, str) and lab in s)
            if not node or not node.parent:
                continue
            txt = node.parent.get_text(" ", strip=True)
            if not txt:
                continue
            lab_txt = node.get_text(" ", strip=True)
            # Strip label prefix and common separators.
            txt = txt.replace(lab_txt, "", 1).strip().lstrip(":：").strip()
            if txt and len(txt) >= 10:
                plot = txt
                break

        # NOTE: Do NOT fall back to meta description here.
        # Many upstream sites use a generic site slogan for meta description,
        # which would pollute plot and block other sources due to merge ordering.
        if plot and _looks_generic_site_desc(plot):
            plot = ""

        data = {
            "number": code,
            "originaltitle": originaltitle,
            "studio": studio,
            "publisher": publisher or studio,
            "series": series,
            "plot": plot,
            "release": release_norm,
            "runtime": runtime_min,
            "directors": directors,
            "actors": actors,
            "tags": tags,
            "cover_url": cover_url,
            "poster_url": poster_url or cover_url,
            "fanart_url": cover_url,
            "preview_urls": preview_urls,
            "trailer_url": trailer_url,
        }

        if rating:
            data["rating"] = rating

        return CrawlResult(
            source=self.name,
            title=title or code,
            external_id=code,
            original_url=detail_url,
            data=data,
        )

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        code = self._extract_code(file_path)
        if not code:
            return None

        search_url = f"{self.cfg.base_url}/search?q={quote_plus(code)}&locale=zh"
        search_html = self._get_text(search_url)
        if not search_html:
            return None

        detail_url = self._find_first_detail_url(search_html, code)
        if not detail_url:
            return None

        detail_html = self._get_text(detail_url)
        if not detail_html:
            return None

        return self._parse_detail(detail_url, detail_html, code)
