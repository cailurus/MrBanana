"""
Jable.tv 视频信息提取器
"""
import re
from html import unescape
from urllib.parse import urljoin
from typing import Optional, Dict, Any
from mr_banana.extractors.base import BaseExtractor
from mr_banana.utils.logger import logger


class JableExtractor(BaseExtractor):
    """从 jable.tv 提取视频信息"""

    def can_handle(self, url: str) -> bool:
        """检查是否为 jable.tv 链接"""
        return "jable.tv" in url

    def extract(self, url: str) -> Optional[Dict[str, Any]]:
        """
        提取视频信息
        
        Returns:
            包含 id, title, video_url, metadata 的字典
        """
        logger.info(f"Extracting video info from {url}")

        page_html: str | None = None

        # Try curl_cffi direct mode first if cookies are available (fast, no browser)
        if self.network.cookies:
            logger.info("Cookies detected, trying direct curl_cffi mode (no browser)...")
            page_html = self.network.get(url, use_browser=False)
            if page_html and self._get_m3u8_url(page_html):
                logger.info("Direct curl_cffi mode succeeded (cookie bypass)")
            else:
                logger.info("Direct curl_cffi mode failed or no m3u8 found, falling back to browser")
                page_html = None

        # Fallback: browser mode (launches Chromium via Patchright)
        if not page_html:
            logger.info("Using browser mode (Patchright Chromium) to bypass Cloudflare")
            page_html = self.network.get(url, use_browser=True)

        if not page_html:
            logger.error("Failed to fetch page HTML")
            return None

        video_url = self._get_m3u8_url(page_html)
        if not video_url:
            logger.error("Failed to extract m3u8 URL")
            return None

        movie_id = self._get_movie_id(url)
        title = self._get_title(page_html) or movie_id

        metadata = {
            "original_url": url,
        }

        try:
            title_from_meta = self._get_title(page_html)
            if title_from_meta:
                title = title_from_meta
        except Exception:
            logger.debug("Jable: failed to extract title")

        try:
            og_image = self._get_og_image(page_html)
            if og_image:
                metadata["cover_url"] = og_image
                metadata.setdefault("poster_url", og_image)
                metadata.setdefault("fanart_url", og_image)
        except Exception:
            logger.debug("Jable: failed to extract og:image")

        try:
            plot = self._get_og_description(page_html)
            if plot:
                metadata["plot"] = plot
        except Exception:
            logger.debug("Jable: failed to extract plot")

        try:
            release = self._get_release_date(page_html)
            if release:
                metadata["release"] = release
        except Exception:
            logger.debug("Jable: failed to extract release date")

        try:
            actors = self._get_actors(page_html, base_url=url)
            if actors:
                metadata["actors"] = actors
        except Exception:
            logger.debug("Jable: failed to extract actors")

        try:
            tags = self._get_tags(page_html, base_url=url)
            if tags:
                metadata["tags"] = tags
        except Exception:
            logger.debug("Jable: failed to extract tags")

        try:
            preview_urls = self._get_preview_images(page_html, base_url=url)
            if preview_urls:
                metadata["preview_urls"] = preview_urls
        except Exception:
            logger.debug("Jable: failed to extract preview images")

        return {
            "id": movie_id,
            "title": title,
            "video_url": video_url,
            "metadata": metadata,
        }

    def _get_movie_id(self, url: str) -> str:
        """从 URL 提取视频 ID"""
        # 示例: https://jable.tv/videos/mida-246/ -> mida-246
        clean_url = url.rstrip('/')
        return clean_url.split('/')[-1]

    def _get_title(self, html: str) -> Optional[str]:
        """从 HTML 提取视频标题"""
        # 优先使用 Open Graph 标题
        match = re.search(r'<meta property="og:title" content="(.*?)"', html)
        if match:
            return match.group(1).strip()

        # 备选：使用 title 标签
        match = re.search(r"<title>(.*?)</title>", html)
        if match:
            return match.group(1).replace(" - Jable.TV", "").strip()
        return None

    def _get_m3u8_url(self, html: str) -> Optional[str]:
        """从 HTML 提取 m3u8 视频链接"""
        match = re.search(r'hlsUrl\s*=\s*["\'](.*?)["\']', html)
        if match:
            return match.group(1)
        return None

    def _get_og_image(self, html: str) -> Optional[str]:
        match = re.search(r'<meta\s+property="og:image"\s+content="(.*?)"', html)
        if match:
            return unescape(match.group(1).strip())
        match = re.search(r'<meta\s+name="twitter:image"\s+content="(.*?)"', html)
        if match:
            return unescape(match.group(1).strip())
        return None

    def _get_og_description(self, html: str) -> Optional[str]:
        match = re.search(r'<meta\s+property="og:description"\s+content="(.*?)"', html)
        if match:
            return unescape(match.group(1).strip())
        match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html)
        if match:
            return unescape(match.group(1).strip())
        return None

    def _get_release_date(self, html: str) -> Optional[str]:
        # Common ISO formats
        m = re.search(r"\b(20\d{2})[-/](0?\d{1,2})[-/](0?\d{1,2})\b", html)
        if m:
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            return f"{y}-{mo}-{d}"
        return None

    def _get_actors(self, html: str, base_url: str) -> list[str]:
        # Use BeautifulSoup if available; fall back to regex.
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            names: list[str] = []
            seen = set()
            for a in soup.find_all("a"):
                href = a.get("href") or ""
                href = urljoin(base_url, href)
                if "/models/" not in href and "/model/" not in href:
                    continue
                text = (a.get_text() or "").strip()
                if not text:
                    continue
                if text in seen:
                    continue
                seen.add(text)
                names.append(text)
            return names
        except Exception:
            pass

        # Regex fallback: href contains /models/
        names = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="([^"]*/models/[^\"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            text = re.sub(r"<.*?>", "", m.group(2))
            text = unescape(text).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            names.append(text)
        return names

    def _get_tags(self, html: str, base_url: str) -> list[str]:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            tags: list[str] = []
            seen = set()
            for a in soup.find_all("a"):
                href = a.get("href") or ""
                href = urljoin(base_url, href)
                if "/tags/" not in href and "/categories/" not in href:
                    continue
                text = (a.get_text() or "").strip()
                if not text:
                    continue
                if text in seen:
                    continue
                seen.add(text)
                tags.append(text)
            return tags
        except Exception:
            pass

        tags = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="([^"]*/(?:tags|categories)/[^\"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            text = re.sub(r"<.*?>", "", m.group(2))
            text = unescape(text).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            tags.append(text)
        return tags

    def _get_preview_images(self, html: str, base_url: str) -> list[str]:
        urls: list[str] = []
        seen = set()

        # Prefer <video poster="...">
        m = re.search(r'<video[^>]+poster="(.*?)"', html)
        if m:
            u = urljoin(base_url, unescape(m.group(1).strip()))
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

        # Collect a few likely preview images
        for m in re.finditer(r'(https?://[^\s"\']+\.(?:jpg|jpeg|png|webp))', html, re.IGNORECASE):
            u = unescape(m.group(1))
            if any(k in u.lower() for k in ("preview", "thumb", "thumbnail", "cover", "poster")):
                if u not in seen:
                    seen.add(u)
                    urls.append(u)
            if len(urls) >= 10:
                break

        return urls

    @staticmethod
    def extract_grid_thumbnails(html: str, base_url: str = "https://jable.tv") -> list[dict]:
        """Extract video thumbnails from jable.tv grid pages (liked/watch-later).

        Returns list of { code, title, url, thumbnail_url } dicts.
        """
        results: list[dict] = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.video-img-box, div.img-box, a[href*='/videos/']")
            seen = set()
            for card in cards:
                href = ""
                if card.name == "a":
                    href = card.get("href", "")
                else:
                    link = card.select_one("a[href*='/videos/']")
                    if link:
                        href = link.get("href", "")
                if not href or "/videos/" not in href:
                    continue
                href_full = urljoin(base_url, href)
                if href_full in seen:
                    continue
                seen.add(href_full)
                code = href.strip("/").split("/")[-1]
                if not code:
                    continue

                thumb = ""
                img = card.select_one("img")
                if img:
                    # data-src has the real image (lazy-loaded); src is usually a placeholder
                    thumb_src = img.get("data-src") or img.get("src") or ""
                    thumb = urljoin(base_url, thumb_src)
                title = (img.get("alt") or img.get("title") or "").strip() if img else ""
                if not title:
                    title_el = card.select_one(".video-title, .title, h5, h4, h3")
                    if title_el:
                        title = title_el.get_text(strip=True)

                results.append({
                    "code": code,
                    "title": title or code,
                    "url": href_full,
                    "thumbnail_url": thumb,
                })
        except Exception:
            pass
        return results