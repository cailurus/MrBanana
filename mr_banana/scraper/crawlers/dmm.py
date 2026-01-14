from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from curl_cffi import requests

from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler, extract_jav_code


@dataclass
class DmmConfig:
    base_url: str = "https://www.dmm.co.jp"
    request_delay_sec: float = 0.0
    proxy_url: str = ""  # optional


class DmmCrawler(BaseCrawler):
    """Best-effort plot/简介 crawler using DMM public pages.

    Notes:
    - DMM may be region/age-gate restricted.
    - This crawler is intentionally conservative; failures return None.
    """

    name = "dmm"

    def __init__(self, cfg: DmmConfig | None = None, log_fn=None):
        self.cfg = cfg or DmmConfig()
        self._log = log_fn

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    def _extract_code(self, file_path: Path) -> str | None:
        return extract_jav_code(file_path)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6",
        }

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

            # best-effort: bypass age check if present
            cookies = {
                "age_check_done": "1",
            }

            r = requests.get(
                url,
                headers=self._headers(),
                cookies=cookies,
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

    def _looks_placeholder_plot(self, s: str) -> bool:
        t = re.sub(r"\s+", " ", (s or "").strip()).lower()
        if not t:
            return True
        markers = [
            "javascriptを有効",
            "javascriptの設定方法",
            "無料サンプル",
            "サンプル動画",
            "中古品",
            "画像をクリックして拡大",
            "拡大サンプル画像",
        ]
        return any(m in t for m in markers)

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        code = self._extract_code(file_path)
        if not code:
            return None

        search_url = f"{self.cfg.base_url}/search/=/searchstr={quote_plus(code)}/"
        html = self._get_text(search_url)
        if not html:
            return None

        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            # First result link
            a = soup.select_one("a[href*='/-/detail/']")
            if not a or not a.get("href"):
                return None
            detail_url = a.get("href")
            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin(self.cfg.base_url + "/", detail_url)

            detail_html = self._get_text(detail_url)
            if not detail_html:
                return None

            dsoup = BeautifulSoup(detail_html, "html.parser")
            title = ""
            t = dsoup.select_one("h1")
            if t:
                title = t.get_text(" ", strip=True)

            def _dedupe(xs: list[str]) -> list[str]:
                out: list[str] = []
                seen: set[str] = set()
                for x in xs or []:
                    s = re.sub(r"\s+", " ", str(x or "").strip())
                    if not s or s in seen:
                        continue
                    seen.add(s)
                    out.append(s)
                return out

            def _extract_block_by_label(labels: list[str]):
                # Heuristics for DMM detail pages (varies by layout).
                # Try dl/dt/dd first.
                for dt in dsoup.select("dt"):
                    k = dt.get_text(" ", strip=True)
                    if not k:
                        continue
                    if any(lbl in k for lbl in labels):
                        dd = dt.find_next_sibling("dd")
                        if dd:
                            return dd

                # Try table th/td.
                for th in dsoup.select("th"):
                    k = th.get_text(" ", strip=True)
                    if not k:
                        continue
                    if any(lbl in k for lbl in labels):
                        td = th.find_next_sibling("td")
                        if td:
                            return td

                # Fallback: generic label elements.
                for el in dsoup.select(".nw, .d-label, .w100"):
                    k = el.get_text(" ", strip=True)
                    if not k:
                        continue
                    if any(lbl in k for lbl in labels):
                        sib = el.find_next_sibling()
                        if sib:
                            return sib
                return None

            def _extract_list(labels: list[str]) -> list[str]:
                blk = _extract_block_by_label(labels)
                if not blk:
                    return []
                # Prefer linked items.
                items = [a.get_text(" ", strip=True) for a in blk.select("a") if a.get_text(strip=True)]
                if items:
                    return _dedupe(items)
                txt = blk.get_text(" ", strip=True)
                if not txt:
                    return []
                # Split on common separators.
                parts = re.split(r"\s*(?:,|，|/|／|\||・)\s*", txt)
                return _dedupe([p for p in parts if p])

            def _extract_text(labels: list[str]) -> str:
                blk = _extract_block_by_label(labels)
                if not blk:
                    return ""
                txt = blk.get_text(" ", strip=True)
                return re.sub(r"\s+", " ", txt).strip()

            actors = _extract_list(["出演者", "出演", "女優"])
            tags = _extract_list(["ジャンル", "カテゴリ", "カテゴリー"])
            maker = _extract_text(["メーカー", "制作"])
            label = _extract_text(["レーベル"])
            series = _extract_text(["シリーズ"])
            director = _extract_text(["監督"])
            release = _extract_text(["発売日", "商品発売日", "配信開始日", "配信日"])
            runtime = _extract_text(["収録時間", "再生時間", "時間"])
            # Normalize runtime to minutes if a number exists.
            runtime_min = ""
            try:
                m_rt = re.search(r"(\d{1,4})\s*分", runtime)
                if m_rt:
                    runtime_min = str(int(m_rt.group(1)))
                else:
                    m_rt2 = re.search(r"\b(\d{1,4})\b", runtime)
                    if m_rt2:
                        runtime_min = str(int(m_rt2.group(1)))
            except Exception:
                runtime_min = ""

            def _clean_meta_description_to_plot(s: str, *, code_hint: str) -> str:
                txt = re.sub(r"\s+", " ", (s or "")).strip()
                if not txt:
                    return ""

                # Remove common leading metadata blocks in Chinese descriptions.
                # Example:
                # [发布日期] 2025-10-30，[时长] 123 分钟，(WAAA-585)“<title>”<plot>
                # Be tolerant to punctuation/spacing.
                for _ in range(3):
                    before = txt
                    txt = re.sub(r"^\s*(?:\[|［)\s*发布日期\s*(?:\]|］)\s*[^，,]+\s*[，,]\s*", "", txt)
                    txt = re.sub(r"^\s*(?:\[|［)\s*时长\s*(?:\]|］)\s*\d+\s*分钟\s*[，,]\s*", "", txt)
                    if txt == before:
                        break

                # Remove leading (CODE) marker (halfwidth/fullwidth parentheses).
                if code_hint:
                    txt = re.sub(rf"^[\(（]\s*{re.escape(code_hint)}\s*[\)）]\s*", "", txt, flags=re.IGNORECASE)
                txt = re.sub(r"^[\(（][A-Za-z0-9]+-[A-Za-z0-9]+[\)）]\s*", "", txt)

                # Strip marketing prefixes that aren't plot.
                txt = re.sub(r"^\[[^\]]+\]\s*", "", txt)  # leading [xxx]
                txt = re.sub(r"^【[^】]+】\s*", "", txt)      # leading 【xxx】

                # If it starts with a quoted long title, drop that title part.
                # Handles: “...”, 「...」, 『...』
                txt = re.sub(r"^(?:“[^”]{5,200}”|「[^」]{5,200}」|『[^』]{5,200}』)\s*", "", txt)

                # Some descriptions repeat the title without quotes; if we have a very long title, trim it off.
                if title and len(title) >= 40 and txt.startswith(title):
                    txt = txt[len(title):].lstrip(" :：-—，,")

                return re.sub(r"\s+", " ", txt).strip()

            plot = ""
            # Prefer real synopsis blocks over meta description.
            # Different DMM layouts (digital, rental/ppr, dvd) use varying selectors.
            for sel in [
                # User-confirmed selector for rental/ppr pages
                ".mg-t0.mg-b20",
                # PPR/rental layout (e.g., /rental/ppr/-/detail/...)
                ".m-boxDetailProduct__info__txt",
                ".m-boxDetailProduct__info p",
                "div.m-boxDetailProduct__info",
                # Digital/standard detail layout
                "#mu .mg-b20",
                "#mu .mg-b20.lh4",
                "#mu p",
                ".mg-b20.lh4",
                ".mg-b20",
                ".summary",
                ".productDetail__txt",
                # Fallback: any paragraph in common detail containers
                ".product-detail p",
                ".detail-txt p",
                ".product-info p",
            ]:
                cand = dsoup.select_one(sel)
                if not cand:
                    continue
                txt = cand.get_text(" ", strip=True)
                txt = re.sub(r"\s+", " ", txt).strip()
                if not txt:
                    continue

                # Some DMM pages include the same meta-style prefix even in visible blocks.
                if ("发布日期" in txt and "时长" in txt and "分钟" in txt) or re.match(r"^[\(（][A-Za-z0-9]+-[A-Za-z0-9]+[\)）]", txt):
                    txt = _clean_meta_description_to_plot(txt, code_hint=code)

                if txt and len(txt) >= 30:
                    plot = txt
                    break

            # Fallback: meta description, but clean off metadata/title prefix.
            if not plot:
                meta = dsoup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    raw = str(meta.get("content") or "").strip()
                    cleaned = _clean_meta_description_to_plot(raw, code_hint=code)
                    # Keep only if it looks like a real plot.
                    if cleaned and len(cleaned) >= 30:
                        plot = cleaned

            plot = re.sub(r"\s+", " ", plot).strip()

            # Trailer / sample video (best effort)
            trailer_url = ""
            try:
                # Try structured video/source tags first
                for sel in [
                    "video source[src]",
                    "video[src]",
                    "a[href$='.mp4']",
                    "a[href*='.mp4']",
                    "a[href$='.m3u8']",
                    "a[href*='.m3u8']",
                ]:
                    el = dsoup.select_one(sel)
                    if not el:
                        continue
                    cand = el.get("src") or el.get("href")
                    if not cand:
                        continue
                    cand = str(cand).strip()
                    if cand.startswith("//"):
                        cand = "https:" + cand
                    elif cand.startswith("/"):
                        cand = urljoin(self.cfg.base_url + "/", cand)
                    if cand.startswith("http://") or cand.startswith("https://"):
                        trailer_url = cand
                        break
            except Exception:
                trailer_url = ""

            if not trailer_url:
                # Fallback: scan raw HTML for direct video URLs.
                try:
                    urls = [
                        m.group(0)
                        for m in re.finditer(
                            r"(?:https?:)?//[^\"\'\s<>]+\.(?:mp4|m3u8)(?:\?[^\"\'\s<>]+)?",
                            detail_html,
                            flags=re.IGNORECASE,
                        )
                    ]
                    if urls:
                        cand = str(urls[0]).strip()
                        if cand.startswith("//"):
                            cand = "https:" + cand
                        trailer_url = cand
                except Exception:
                    trailer_url = ""

            if plot and self._looks_placeholder_plot(plot):
                self._emit("plot looks like JS/blocked placeholder; dropping")
                plot = ""

            if not title and not plot:
                return None

            data = {
                "number": code,
                "plot": plot,
                "trailer_url": trailer_url,
            }

            if actors:
                data["actors"] = actors
            if tags:
                data["tags"] = tags
            if maker:
                data["studio"] = maker
            if label:
                data["publisher"] = label
            elif maker:
                # Keep backward-compatible behavior when no label is present.
                data["publisher"] = maker
            if series:
                data["series"] = series
            if director:
                data["directors"] = [director]
            if release:
                data["release"] = release
            if runtime_min:
                data["runtime"] = runtime_min

            return CrawlResult(
                source=self.name,
                title=title or code,
                external_id=code,
                original_url=detail_url,
                data=data,
            )
        except Exception as e:
            self._emit(f"!! parse error dmm: {e}")
            return None
