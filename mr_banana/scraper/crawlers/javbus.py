from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from curl_cffi import requests

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler


@dataclass
class JavbusConfig:
    base_url: str = "https://www.javbus.com"
    cookie: str = ""  # optional
    request_delay_sec: float = 0.0
    proxy_url: str = ""  # optional


class JavbusCrawler(BaseCrawler):
    """Scrape metadata from JavBus (free, no account required for basic pages).

    Notes:
    - JavBus availability varies by region and may apply rate limiting.
    - We do not require cookies; if the site blocks, we'll log the failure.
    """

    name = "javbus"

    def __init__(self, cfg: JavbusConfig | None = None, log_fn=None):
        self.cfg = cfg or JavbusConfig()
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

    def _is_blocked(self, html: str) -> str | None:
        low = (html or "").lower()
        if "lostpasswd" in low:
            return "blocked: requires cookie/login"
        if "cloudflare" in low and "ray id" in low:
            return "blocked: cloudflare"
        return None

    def _parse_detail(self, detail_url: str, html: str, code: str) -> CrawlResult | None:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            # Best-effort validation: ensure the page looks like the requested code.
            # This avoids accepting near matches that would produce wrong titles/plots.
            def _norm(s: str) -> str:
                return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())

            want = _norm(code)
            if want:
                m = re.search(r"\b[A-Za-z0-9]{2,10}-[A-Za-z0-9]{2,10}\b", html or "", flags=re.IGNORECASE)
                if m and _norm(m.group(0)) != want:
                    self._emit(f"skip detail: id mismatch want={code} got={m.group(0)}")
                    return None

            soup = BeautifulSoup(html, "html.parser")

            title = ""
            h3 = soup.find("h3")
            if h3:
                title = h3.get_text(" ", strip=True)

            # cover
            cover_url = ""
            big = soup.select_one("a.bigImage")
            if big and big.get("href"):
                cover_url = big.get("href")
                if cover_url and not cover_url.startswith("http"):
                    cover_url = urljoin(self.cfg.base_url + "/", cover_url)

            # poster (smaller)
            poster_url = ""
            if cover_url:
                # mimic mdcx logic
                if "/pics/" in cover_url:
                    poster_url = cover_url.replace("/cover/", "/thumb/").replace("_b.jpg", ".jpg")
                elif "/imgs/" in cover_url:
                    poster_url = cover_url.replace("/cover/", "/thumbs/").replace("_b.jpg", ".jpg")

            # release/runtime/studio/publisher/series/director
            def _text_after(header_text: str) -> str:
                node = soup.find("span", class_="header", string=lambda s: isinstance(s, str) and header_text in s)
                if not node or not node.parent:
                    return ""
                # parent contains header and value nodes
                txt = node.parent.get_text(" ", strip=True)
                # strip header
                return txt.replace(header_text, "").strip(":： ")

            release = _text_after("發行日期") or _text_after("发行日期")
            runtime_raw = _text_after("長度") or _text_after("长度")
            runtime = ""
            if runtime_raw:
                m = re.search(r"(\d+)", runtime_raw)
                runtime = m.group(1) if m else ""

            studio = ""
            a = soup.select_one("a[href*='/studio/']")
            if a:
                studio = a.get_text(" ", strip=True)
            publisher = ""
            a = soup.select_one("a[href*='/label/']")
            if a:
                publisher = a.get_text(" ", strip=True)
            publisher = publisher or studio

            director = []
            for a in soup.select("a[href*='/director/']"):
                t = a.get_text(" ", strip=True)
                if t:
                    director.append(t)
            director = list(dict.fromkeys(director))

            series = ""
            a = soup.select_one("a[href*='/series/']")
            if a:
                series = a.get_text(" ", strip=True)

            # actors
            actors = []
            for a in soup.select("div.star-name a"):
                t = a.get_text(" ", strip=True)
                if t:
                    actors.append(t)
            actors = list(dict.fromkeys(actors))

            # tags
            tags = []
            for a in soup.select("span.genre a[href*='/genre/']"):
                t = a.get_text(" ", strip=True)
                if t:
                    tags.append(t)
            tags = list(dict.fromkeys(tags))

            def _looks_generic_site_desc(s: str) -> bool:
                t = (s or "").strip()
                if not t:
                    return True
                bad_markers = [
                    "番号搜磁链",
                    "管理你的成人影片",
                    "分享你的想法",
                ]
                if any(m in t for m in bad_markers):
                    return True
                if len(t) < 30:
                    return True
                return False

            def _looks_meta_blob_plot(s: str) -> bool:
                t = (s or "").strip()
                if not t:
                    return True
                # Common JavBus pattern (Traditional Chinese):
                # 【發行日期】YYYY-MM-DD，【長度】123分鐘，(CODE)「TITLE」...
                if ("發行日期" in t or "发行日期" in t or "发布日期" in t) and ("長度" in t or "长度" in t or "时长" in t) and ("分鐘" in t or "分钟" in t):
                    return True
                if "(" in t and ")" in t and re.search(r"\b[A-Za-z0-9]+-[A-Za-z0-9]+\b", t):
                    # If it looks like a header line and is short, treat as meta.
                    if len(t) < 180:
                        return True
                return False

            # plot / description (best effort)
            plot = ""
            # common text block
            block = soup.select_one("div.mg-b20.lh4")
            if block:
                plot = block.get_text(" ", strip=True)
            if not plot:
                for lab in ["簡介", "简介", "Description", "Storyline", "剧情", "劇情"]:
                    node = soup.find("span", class_="header", string=lambda s: isinstance(s, str) and lab in s)
                    if not node or not node.parent:
                        continue
                    txt = node.parent.get_text(" ", strip=True)
                    if not txt:
                        continue
                    txt = txt.replace(node.get_text(" ", strip=True), "", 1).strip().lstrip(":：").strip()
                    if txt and len(txt) >= 10:
                        plot = txt
                        break
            if not plot:
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    cand = str(meta.get("content") or "").strip()
                    if not _looks_generic_site_desc(cand):
                        plot = cand

            # JavBus sometimes only exposes a metadata line as "plot"; treat that as empty.
            if plot and _looks_meta_blob_plot(plot):
                plot = ""

            # extra fanart
            preview_urls = []
            for a in soup.select("div#sample-waterfall a"):
                href = a.get("href")
                if not href:
                    continue
                if not href.startswith("http"):
                    href = urljoin(self.cfg.base_url + "/", href)
                preview_urls.append(href)
            preview_urls = list(dict.fromkeys(preview_urls))

            # normalize release to yyyy-mm-dd
            release_norm = ""
            if release:
                m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", release)
                if m:
                    y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
                    release_norm = f"{y}-{mo}-{d}"
            release_norm = release_norm or release

            data = {
                "number": code,
                "studio": studio,
                "publisher": publisher,
                "series": series,
                "release": release_norm,
                "runtime": runtime,
                "directors": director,
                "actors": actors,
                "tags": tags,
                "plot": plot,
                "cover_url": cover_url,
                "poster_url": poster_url or cover_url,
                "fanart_url": cover_url,
                "preview_urls": preview_urls,
            }

            return CrawlResult(
                source=self.name,
                title=title or code,
                external_id=code,
                original_url=detail_url,
                data=data,
            )
        except Exception as e:
            self._emit(f"!! parse error {detail_url}: {e}")
            return None

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        code = self._extract_code(file_path)
        if not code:
            return None

        # Try direct detail page first
        direct_url = urljoin(self.cfg.base_url + "/", code)
        html = self._get_text(direct_url)
        if html:
            if reason := self._is_blocked(html):
                self._emit(f"!! {reason} at {direct_url}")
            else:
                res = self._parse_detail(direct_url, html, code)
                if res:
                    self._emit(f"ok {code} via direct")
                    return res

        # Fallback to search
        search_url = urljoin(self.cfg.base_url + "/", f"search/{quote(code)}")
        search_html = self._get_text(search_url)
        if not search_html:
            return None
        if reason := self._is_blocked(search_html):
            self._emit(f"!! {reason} at {search_url}")
            return None

        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(search_html, "html.parser")
            links = soup.select("a.movie-box")
            if not links:
                self._emit(f"miss {code}: no search results")
                return None

            want = re.sub(r"[^A-Za-z0-9]", "", code.upper())
            pick = None
            for a in links:
                href = a.get("href")
                if not href:
                    continue
                upper = href.upper().replace("-", "").replace("_", "")
                if upper.endswith("/" + want) or ("/" + want + "_") in upper:
                    pick = href
                    break
            if not pick:
                pick = links[0].get("href")
            if not pick:
                return None

            detail_url = pick if pick.startswith("http") else urljoin(self.cfg.base_url + "/", pick)
            detail_html = self._get_text(detail_url)
            if not detail_html:
                return None
            if reason := self._is_blocked(detail_html):
                self._emit(f"!! {reason} at {detail_url}")
                return None

            res = self._parse_detail(detail_url, detail_html, code)
            if res:
                self._emit(f"ok {code} via search")
            else:
                self._emit(f"miss {code}: parse failed")
            return res
        except Exception as e:
            self._emit(f"!! search parse error {search_url}: {e}")
            return None
