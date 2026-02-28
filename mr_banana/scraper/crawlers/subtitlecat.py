from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi import requests

from mr_banana.utils.network import DEFAULT_USER_AGENT, build_proxies
from ..types import CrawlResult, MediaInfo
from .base import BaseCrawler


class SubtitleCatCrawler(BaseCrawler):
    """
    Subtitle downloader using subtitlecat.com.
    This is not a metadata crawler, but we implement a similar interface for consistency
    and potential future metadata extraction.
    """
    name = "subtitlecat"
    BASE_URL = "https://subtitlecat.com"

    def __init__(self, proxy_url: str | None = None, log_fn=None):
        self.proxy_url = proxy_url
        self._log = log_fn

    def _emit(self, msg: str) -> None:
        if self._log:
            try:
                self._log(msg)
            except Exception:
                pass

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _get_proxies(self):
        return build_proxies(self.proxy_url)

    def crawl(self, file_path: Path, media: MediaInfo) -> CrawlResult | None:
        # This crawler is special: it doesn't return metadata for merging.
        # It performs a side-effect (downloading subtitles) if invoked directly.
        # However, the runner will likely call specific methods on it.
        return None

    def search_and_download(self, keyword: str, save_path_base: Path, languages: list[str] | None = None) -> list[Path]:
        """
        Search for subtitles and download them.
        :param keyword: The search keyword (e.g. code like SSIS-062)
        :param save_path_base: The base path for saving the subtitle (without extension)
        :param languages: List of preferred languages (e.g. ['zh', 'ja']). 
                          If None, defaults to zh-CN/zh.
        :return: List of downloaded file paths.
        """
        if not keyword:
            return []

        self._emit(f"subtitlecat: searching for '{keyword}'")
        search_url = f"{self.BASE_URL}/index.php"
        params = {"search": keyword}

        try:
            r = requests.get(
                search_url, 
                params=params, 
                headers=self._headers(), 
                impersonate="chrome", 
                timeout=30, 
                proxies=self._get_proxies()
            )
            if r.status_code != 200:
                self._emit(f"subtitlecat: search failed {r.status_code}")
                return []
            
            # Simple regex parsing to avoid lxml dependency if possible, or use lxml if available.
            # The project seems to use lxml in other crawlers (jav321).
            from lxml import etree
            tree = etree.HTML(r.text)
            
            # Find first result
            # Try table rows
            rows = tree.xpath("//table//tbody//tr")
            if not rows:
                rows = tree.xpath("//tr")
            
            if not rows:
                self._emit("subtitlecat: no results found")
                return []

            # Pick the first valid result
            detail_url = None
            for row in rows[:3]:
                links = row.xpath(".//td[1]//a")
                if links:
                    href = links[0].get("href")
                    if href:
                        detail_url = urljoin(self.BASE_URL, href)
                        break
            
            if not detail_url:
                self._emit("subtitlecat: no detail link found")
                return []

            self._emit(f"subtitlecat: found detail {detail_url}")
            return self._process_detail_page(detail_url, save_path_base, languages)

        except Exception as e:
            self._emit(f"subtitlecat: error {e}")
            return []

    def _process_detail_page(self, url: str, save_path_base: Path, languages: list[str] | None) -> list[Path]:
        try:
            r = requests.get(
                url, 
                headers=self._headers(), 
                impersonate="chrome", 
                timeout=30, 
                proxies=self._get_proxies()
            )
            if r.status_code != 200:
                return []

            from lxml import etree
            tree = etree.HTML(r.text)
            
            downloaded_files = []
            
            # Default to zh/ja if not specified
            langs = languages or ["zh", "ja"]
            
            # Map language codes to subtitlecat specific IDs or classes if possible
            # subtitlecat usually has id="download_zh-CN" or "download_ja"
            
            # We will try to find downloads for each requested language
            # If multiple languages are requested, we might download multiple files
            # e.g. video.zh.srt, video.ja.srt
            
            found_any = False
            
            for lang in langs:
                download_url = None
                lang_suffix = ""
                
                if "zh" in lang.lower() or "cn" in lang.lower():
                    # Try Chinese
                    candidates = tree.xpath("//a[@id='download_zh-CN']/@href")
                    if not candidates:
                        candidates = tree.xpath("//a[@id='download_zh']/@href")
                    if candidates:
                        download_url = candidates[0]
                        lang_suffix = ".zh"
                
                elif "ja" in lang.lower() or "jp" in lang.lower():
                    # Try Japanese
                    candidates = tree.xpath("//a[@id='download_ja']/@href")
                    if candidates:
                        download_url = candidates[0]
                        lang_suffix = ".ja"
                
                # If specific language not found, and it's the first language in our list, 
                # maybe try a generic download if we haven't found anything yet?
                # But user asked for specific languages.
                
                if download_url:
                    full_dl_url = urljoin(self.BASE_URL, download_url)
                    ext = ".srt"
                    if ".ass" in full_dl_url:
                        ext = ".ass"
                    elif ".vtt" in full_dl_url:
                        ext = ".vtt"
                    
                    # Naming convention: video.zh.srt
                    # If save_path_base is /path/to/video (without ext), 
                    # we want /path/to/video.zh.srt
                    
                    # Check if we already downloaded this exact file (avoid duplicates if langs overlap)
                    final_path = save_path_base.parent / f"{save_path_base.name}{lang_suffix}{ext}"
                    
                    if self._download_file(full_dl_url, final_path):
                        downloaded_files.append(final_path)
                        found_any = True

            # Fallback: if no specific language found, and we haven't downloaded anything,
            # try to find ANY download link if the user didn't strictly forbid it?
            # For now, let's stick to the requested languages. 
            # If the user wants "default", we might want to grab whatever is there.
            # But the prompt said "download Japanese and Simplified Chinese".
            
            return downloaded_files

        except Exception as e:
            self._emit(f"subtitlecat: detail error {e}")
            return []

    def _download_file(self, url: str, path: Path) -> bool:
        self._emit(f"subtitlecat: downloading {url} -> {path.name}")
        try:
            r = requests.get(
                url, 
                headers=self._headers(), 
                impersonate="chrome", 
                timeout=60, 
                proxies=self._get_proxies()
            )
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
                self._emit(f"subtitlecat: saved {path.name}")
                return True
            else:
                self._emit(f"subtitlecat: download failed {r.status_code}")
                return False
        except Exception as e:
            self._emit(f"subtitlecat: download error {e}")
            return False
