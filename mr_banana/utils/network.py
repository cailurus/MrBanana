"""
网络请求模块 - 支持普通请求和浏览器模式
"""
from __future__ import annotations

import socket
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from curl_cffi import requests, CurlOpt
from mr_banana.utils.logger import logger
from mr_banana.utils.browser import BrowserManager

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Windows variant used by NetworkHandler/HLS downloader for different TLS fingerprint
WINDOWS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _system_resolve(url: str) -> list[bytes]:
    """Pre-resolve hostname using system DNS for curl_cffi c-ares compatibility.

    curl_cffi bundles libcurl compiled with c-ares, which performs its own DNS
    queries and bypasses the system resolver. This breaks proxy tools that
    intercept DNS at the system level (e.g. Clash/Surge Fake-IP mode).

    This function resolves via Python's socket (which uses the system resolver)
    and returns CURLOPT_RESOLVE entries so curl_cffi skips its own DNS lookup.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return []
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addrs = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if addrs:
            ip = addrs[0][4][0]
            return [f"{hostname}:{port}:{ip}".encode()]
    except Exception:
        pass
    return []


def apply_curl_dns_resolve(session: requests.Session, url: str) -> None:
    """Inject system-resolved DNS entries into a curl_cffi Session."""
    entries = _system_resolve(url)
    if not entries:
        return
    existing = session.curl_options.get(CurlOpt.RESOLVE, [])
    new_host_prefix = entries[0].split(b":")[0] + b":"
    # Replace existing entry for the same host, keep others
    updated = [e for e in existing if not e.startswith(new_host_prefix)]
    updated.extend(entries)
    session.curl_options[CurlOpt.RESOLVE] = updated


def build_proxies(proxy_url: str | None) -> dict[str, str] | None:
    """Build a proxies dict from a single proxy URL string.

    Returns None when proxy_url is empty/None (meaning: no proxy).
    """
    pu = str(proxy_url or "").strip()
    if not pu:
        return None
    return {"http": pu, "https": pu}


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
            "User-Agent": WINDOWS_USER_AGENT,
        }
        self._session = requests.Session()
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
        apply_curl_dns_resolve(self._session, url)
        for attempt in range(self.retry):
            try:
                merged_headers = dict(self.headers)
                if headers:
                    merged_headers.update(headers)
                response = self._session.get(
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
        apply_curl_dns_resolve(self._session, url)
        for attempt in range(self.retry):
            try:
                merged_headers = dict(self.headers)
                if headers:
                    merged_headers.update(headers)
                response = self._session.get(
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