"""
网络请求模块 - 支持普通请求和浏览器模式
"""
import time
from typing import Optional, Dict, Any
from curl_cffi import requests
from mr_banana.utils.logger import logger
from mr_banana.utils.browser import BrowserManager


class NetworkHandler:
    """网络请求处理器"""

    def __init__(
        self,
        retry: int = 3,
        delay: int = 2,
        timeout: int = 10,
        proxies: Optional[Dict[str, str]] = None
    ):
        self.retry = retry
        self.delay = delay
        self.timeout = timeout
        self.proxies = proxies
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        proxy_url = None
        try:
            if proxies:
                proxy_url = proxies.get("https") or proxies.get("http")
        except Exception:
            proxy_url = None
        self.browser_manager = BrowserManager(proxy_url=proxy_url)

    def get(self, url: str, use_browser: bool = False, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        GET 请求
        
        Args:
            url: 请求 URL
            use_browser: 是否使用浏览器模式（用于绕过 Cloudflare）
        """
        if use_browser:
            # Browser mode currently does not support per-request headers.
            return self._get_with_browser(url)
        return self._get_with_requests(url, headers=headers)

    def _get_with_requests(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """使用 requests 发起请求"""
        for attempt in range(self.retry):
            try:
                merged_headers = dict(self.headers)
                if headers:
                    merged_headers.update(headers)
                response = requests.get(
                    url=url,
                    headers=merged_headers,
                    timeout=self.timeout,
                    verify=False,
                    proxies=self.proxies,
                    impersonate="chrome"
                )
                if response.status_code == 200:
                    return response.text
                logger.warning(f"HTTP {response.status_code}: {url}")
            except Exception as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{self.retry}): {e}")
                time.sleep(self.delay)
        return None

    def _get_with_browser(self, url: str) -> Optional[str]:
        """使用浏览器发起请求（绕过 Cloudflare）"""
        for attempt in range(self.retry):
            content = self.browser_manager.scrape_page(url)
            if content:
                if "Just a moment..." not in content:
                    return content
                logger.warning(f"Cloudflare challenge not passed (attempt {attempt + 1}/{self.retry})")
            time.sleep(self.delay)
        return None

    def download_file(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
        """下载二进制文件"""
        for attempt in range(self.retry):
            try:
                merged_headers = dict(self.headers)
                if headers:
                    merged_headers.update(headers)
                response = requests.get(
                    url=url,
                    headers=merged_headers,
                    timeout=self.timeout,
                    verify=False,
                    proxies=self.proxies,
                    impersonate="chrome"
                )
                if response.status_code == 200:
                    return response.content
            except Exception as e:
                logger.warning(f"Download failed {url}: {e}")
                time.sleep(self.delay)
        return None