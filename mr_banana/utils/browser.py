"""
浏览器自动化模块 - 用于绕过 Cloudflare 等防护
"""
import time
import subprocess
from typing import Optional
from patchright.sync_api import sync_playwright, Page, Browser, BrowserContext
from mr_banana.utils.logger import logger


class BrowserManager:
    """浏览器管理器，用于获取需要 JavaScript 渲染的页面内容"""

    _chromium_checked: bool = False  # Class-level: only run install once per process

    def __init__(self, headless: bool = True, proxy_url: str | None = None):
        self.headless = headless
        self.proxy_url = (proxy_url or "").strip() or None
        self._ensure_patchright_chromium_installed()

    def _ensure_patchright_chromium_installed(self):
        """确保 patchright chromium 已安装（进程内只执行一次）"""
        if BrowserManager._chromium_checked:
            return
        try:
            subprocess.run(
                ["patchright", "install", "chromium"],
                capture_output=True,
                text=True,
                check=False,
            )
            BrowserManager._chromium_checked = True
        except FileNotFoundError:
            logger.error("patchright command not found; please ensure patchright is installed")
            raise
        except Exception as e:
            logger.error(f"Error installing Chromium: {e}")
            raise

    def scrape_page(self, url: str) -> Optional[str]:
        """使用浏览器获取页面内容"""
        logger.info(f"Launching browser to visit: {url}")

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            context = self._create_context(browser)
            page = context.new_page()

            try:
                content = self._process_page(page, url)
                return content
            except Exception as e:
                logger.error(f"Error scraping page: {e}")
                return None
            finally:
                browser.close()

    def _launch_browser(self, p) -> Browser:
        """启动浏览器实例"""
        browser_args = [
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--disable-web-security",
            "--disable-setuid-sandbox",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--window-size=1920,1080",
        ]
        launch_kwargs = {
            "headless": self.headless,
            "args": browser_args,
            "slow_mo": 50,
        }
        if self.proxy_url:
            launch_kwargs["proxy"] = {"server": self.proxy_url}

        return p.chromium.launch(
            **launch_kwargs,
        )

    def _create_context(self, browser: Browser) -> BrowserContext:
        """创建浏览器上下文"""
        return browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            # Use same Chrome version as WINDOWS_USER_AGENT in network.py
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

    def _process_page(self, page: Page, url: str) -> str:
        """处理页面并返回内容"""
        logger.info(f"Visiting: {url}")
        response = page.goto(url, wait_until="domcontentloaded")

        if response:
            logger.info(f"HTTP status: {response.status}")

        self._handle_cloudflare(page)
        self._wait_for_content(page)
        self._scroll_page(page)

        logger.info("Page content retrieved successfully")
        return page.content()

    def _handle_cloudflare(self, page: Page):
        """处理 Cloudflare 验证"""
        title = page.title()
        if "Just a moment" in title or "Checking your browser" in page.content():
            logger.info("Detected Cloudflare challenge...")
            try:
                page.wait_for_function("document.title != 'Just a moment...'", timeout=30000)
                logger.info("Page title changed")
            except Exception:
                logger.warning("Timed out waiting for title change; trying to click challenge...")
                self._click_challenge(page)
                time.sleep(10)

    def _click_challenge(self, page: Page):
        """点击 Cloudflare 验证按钮"""
        selectors = [
            "input[type='checkbox']",
            ".ray-button",
            "#challenge-stage button",
            "button:has-text('Verify')",
            "button:has-text('Continue')",
        ]
        for selector in selectors:
            if page.is_visible(selector):
                logger.info(f"Clicking challenge element: {selector}")
                try:
                    page.click(selector)
                    time.sleep(5)
                    return
                except Exception as e:
                    logger.error(f"Failed to click {selector}: {e}")

    def _wait_for_content(self, page: Page):
        """等待页面内容加载"""
        content_selectors = [
            "h1", ".main-content", "#content", ".video-container",
            "article", "main", ".container", "h3"
        ]
        for selector in content_selectors:
            try:
                page.wait_for_selector(selector, timeout=5000)
                logger.info(f"Found content element: {selector}")
                return
            except Exception:
                continue
        logger.warning("No specific content element found; waiting a fixed duration...")
        time.sleep(5)

    def _scroll_page(self, page: Page):
        """模拟页面滚动"""
        logger.info("Scrolling page...")
        for _ in range(3):
            page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
            time.sleep(1)
