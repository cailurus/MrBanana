"""
Jable.tv API - Fetch liked/watch-later lists, login, batch download
"""
from __future__ import annotations
from typing import List
import time as _time

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from mr_banana.utils.config import load_config, AppConfig, save_config
from mr_banana.utils.network import NetworkHandler, build_proxies
from mr_banana.extractors.jable import JableExtractor
from mr_banana.utils.logger import logger

from api.async_utils import run_sync
from api.dependencies import get_download_manager
from api.manager import DownloadManager

router = APIRouter()


def _merged_jable_cookies() -> dict[str, str]:
    """Merge Cloudflare bypass cookie + session login cookie."""
    cfg = load_config()
    cookies = {}
    if cfg.jable_cookie:
        cookies.update(AppConfig.parse_cookie_string(cfg.jable_cookie))
    if cfg.jable_session_cookie:
        cookies.update(AppConfig.parse_cookie_string(cfg.jable_session_cookie))
    return cookies


class JableLoginRequest(BaseModel):
    username: str
    password: str


class BatchDownloadRequest(BaseModel):
    codes: List[str]
    output_dir: str = ""


@router.get("/api/jable/status")
async def jable_status():
    cfg = load_config()
    return {
        "logged_in": bool(cfg.jable_session_cookie),
        "username": cfg.jable_username or "",
    }


@router.get("/api/jable/lists")
async def get_jable_lists():
    cookies = _merged_jable_cookies()
    if not cookies:
        raise HTTPException(status_code=400, detail="请先登录 Jable.tv")

    proxy_url = None
    cfg = load_config()
    if cfg.download_use_proxy and cfg.download_proxy_url:
        proxy_url = cfg.download_proxy_url

    # Try CDP-based pagination first (clicks through all pages via existing Chrome)
    try:
        liked, watch_later = await run_sync(_scrape_list_via_cdp, cookies, proxy_url)
        return {
            "liked": liked,
            "watch_later": watch_later,
            "liked_count": len(liked),
            "watch_later_count": len(watch_later),
        }
    except Exception as e:
        logger.info(f"CDP list scraping failed, falling back to single-page fetch: {e}")

    # Fallback: single-page curl_cffi fetch (only gets first 24 items)
    network = NetworkHandler(proxies=build_proxies(proxy_url), cookies=cookies)

    liked = []
    watch_later = []

    def _fetch(url):
        if cookies:
            result = network.get(url, use_browser=False)
            if result and "video-img-box" in result:
                return result
        return network.get(url, use_browser=True)

    async def _fetch_page(base_url: str, list_type: str):
        html = await run_sync(_fetch, base_url)
        if html:
            items = JableExtractor.extract_grid_thumbnails(html)
            for item in items:
                code = item.get("code", "")
                if code in ("videos", "videos-watch-later", "my") or not code:
                    continue
                item["list_type"] = list_type
                if list_type == "liked":
                    if code not in {i["code"] for i in liked}:
                        liked.append(item)
                else:
                    if code not in {i["code"] for i in watch_later}:
                        watch_later.append(item)

    await _fetch_page("https://jable.tv/my/favourites/videos/", "liked")
    await _fetch_page("https://jable.tv/my/favourites/videos-watch-later/", "watch_later")

    return {
        "liked": liked,
        "watch_later": watch_later,
        "liked_count": len(liked),
        "watch_later_count": len(watch_later),
    }
def _scrape_list_via_cdp(cookies: dict, proxy_url: str | None) -> tuple[list, list]:
    """Scrape all pages of liked and watch-later lists via CDP Chrome.

    Opens new tabs in the running CDP Chrome, clicks through pagination,
    and collects all video items. Returns (liked, watch_later) lists.
    """
    import http.client, json as _json, time as _t
    from patchright.sync_api import sync_playwright

    # Check if CDP Chrome is running
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=3)
        conn.request("GET", "/json/version")
        resp = conn.getresponse()
        _json.loads(resp.read().decode())
        conn.close()
    except Exception:
        raise RuntimeError("CDP Chrome not running on port 9222")

    liked = []
    watch_later = []

    def _scrape_one_list(list_url: str) -> list[dict]:
        """Navigate to a list page, click through AJAX pagination, return items.

        jable.tv uses AJAX pagination with page links like:
        <a class="page-link" data-parameters="...from_my_fav_videos:02">02</a>
        """
        items = []
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()

            try:
                # Inject cookies before navigating
                if cookies:
                    cookie_list = []
                    for name, value in cookies.items():
                        cookie_list.append({
                            "name": name, "value": value,
                            "domain": "jable.tv", "path": "/",
                            "httpOnly": False, "secure": True, "sameSite": "Lax",
                        })
                    try:
                        context.add_cookies(cookie_list)
                    except Exception:
                        pass

                page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                _t.sleep(3)  # let page fully render

                # Read total page count from pagination
                max_pages = page.evaluate("""() => {
                    const links = document.querySelectorAll('ul.pagination li.page-item a.page-link');
                    let max = 1;
                    links.forEach(l => {
                        const t = l.innerText.trim();
                        if (/^\d+$/.test(t)) max = Math.max(max, parseInt(t));
                    });
                    return max;
                }""")
                logger.info(f"CDP: detected {max_pages} total pages")

                # Scrape page 1 (already loaded)
                html = page.content()
                page_items = JableExtractor.extract_grid_thumbnails(html)
                for item in page_items:
                    code = item.get("code", "")
                    if code not in ("videos", "videos-watch-later", "my") and code:
                        items.append(item)
                logger.info(f"CDP: page 1, {len(page_items)} raw items (total {len(items)} unique so far)")

                # Click through remaining pages using JS to avoid handle staleness
                for pn in range(2, max_pages + 1):
                    clicked = page.evaluate(f"""(pn) => {{
                        const links = document.querySelectorAll('ul.pagination li.page-item a.page-link');
                        for (const l of links) {{
                            if (l.innerText.trim() === String(pn).padStart(2, '0')) {{
                                l.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}""", pn)

                    if not clicked:
                        logger.info(f"CDP: could not click page {pn}, stopping")
                        break

                    _t.sleep(3)  # wait for AJAX

                    html = page.content()
                    page_items = JableExtractor.extract_grid_thumbnails(html)
                    for item in page_items:
                        code = item.get("code", "")
                        if code not in ("videos", "videos-watch-later", "my") and code:
                            items.append(item)
                    logger.info(f"CDP: page {pn}, {len(page_items)} raw items (total {len(items)} unique so far)")

            finally:
                page.close()

        # Deduplicate
        seen = set()
        unique = []
        for item in items:
            code = item.get("code", "")
            if code and code not in seen:
                seen.add(code)
                unique.append(item)
        logger.info(f"CDP: total unique items after dedup: {len(unique)}")
        return unique

    liked_raw = _scrape_one_list("https://jable.tv/my/favourites/videos/")
    for item in liked_raw:
        item["list_type"] = "liked"
        liked.append(item)

    watch_later_raw = _scrape_one_list("https://jable.tv/my/favourites/videos-watch-later/")
    for item in watch_later_raw:
        item["list_type"] = "watch_later"
        watch_later.append(item)

    return liked, watch_later


@router.post("/api/jable/login")
async def jable_login(request: JableLoginRequest):
    """Login to jable.tv.

    First tries to extract cookies from an already-running CDP Chrome
    (started via run.ps1 with --remote-debugging-port=9222).

    If CDP is not available, falls back to launching a new Patchright
    browser window for manual login.
    """
    cfg = load_config()

    # ------------------------------------------------------------------
    # Phase 1: Try CDP Chrome extraction (user already logged in)
    # ------------------------------------------------------------------
    try:
        from mr_banana.utils.config import AppConfig

        import http.client, json as _json
        conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=3)
        try:
            conn.request("GET", "/json")
            resp = conn.getresponse()
            targets = _json.loads(resp.read().decode("utf-8"))
        except Exception:
            targets = []
        finally:
            conn.close()

        # Find a jable.tv page target
        jable_target = None
        for t in targets:
            if t.get("type") == "page" and "jable.tv" in str(t.get("url", "")):
                jable_target = t
                break

        if jable_target:
            logger.info("Found active jable.tv tab in CDP Chrome, extracting cookies...")

            # Check if already logged in (has session cookies like kt_member)
            from scripts.mcp_cdp_cookie_server import extract_cookies_for_domain
            cookies = extract_cookies_for_domain("jable.tv")
            cookie_dict = {}
            for c in cookies:
                cookie_dict[c.get("name", "")] = c.get("value", "")

            # Check for login indicators
            has_member = "kt_member" in cookie_dict
            has_session = "PHPSESSID" in cookie_dict

            if has_member or has_session:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
                logger.info(f"Extracted {len(cookie_dict)} cookies from CDP Chrome (member={has_member})")

                cfg.jable_cookie = cookie_str
                cfg.jable_session_cookie = cookie_str
                cfg.jable_username = request.username or "CDP"
                save_config(cfg)

                return {
                    "status": "ok",
                    "message": "已從 Chrome 會話提取 cookie，登錄成功！",
                    "username": request.username or "CDP",
                }

            logger.info("CDP Chrome tab found but no login session cookies detected")
    except Exception as e:
        logger.info(f"CDP extraction not available: {e}")

    # ------------------------------------------------------------------
    # Phase 2: Fallback - launch visible browser for manual login
    # ------------------------------------------------------------------
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="CDP 未檢測到已登錄會話，請提供用戶名和密碼進行手動登錄")

    proxy_url = cfg.download_proxy_url if cfg.download_use_proxy else None

    def _do_login():
        from patchright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=[
                "--disable-gpu",
                "--no-first-run",
                "--window-size=1280,800",
                "--window-position=100,100",
            ])
            ctx_opts = {
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
            if proxy_url:
                ctx_opts["proxy"] = {"server": proxy_url}
            context = browser.new_context(**ctx_opts)
            page = context.new_page()

            try:
                logger.info("Opening jable.tv login page in visible browser...")
                page.goto("https://jable.tv/login/", wait_until="domcontentloaded", timeout=60000)

                logger.info("Browser window opened. Waiting for user to complete login...")
                logger.info("The window will auto-close after login is detected.")

                max_wait = 300
                for _ in range(max_wait):
                    _time.sleep(1)
                    current_url = page.url
                    if "/login/" not in current_url and "jable.tv" in current_url:
                        logger.info(f"Login detected! URL changed to: {current_url}")
                        _time.sleep(2)
                        break

                    try:
                        has_member = page.query_selector("a[href*='/my/'], a[href*='/members/'], .user-menu, .member-menu, .avatar")
                        if has_member:
                            logger.info("Login detected via member menu element!")
                            _time.sleep(2)
                            break
                    except Exception:
                        pass
                else:
                    current_url = page.url
                    if "/login/" in current_url or "login" in current_url.lower():
                        logger.warning("Login timed out")
                        return {"error": "登录超时（5分钟），请重试"}

                all_cookies = context.cookies()
                result_cookies = {}
                for c in all_cookies:
                    if c["name"] not in result_cookies:
                        result_cookies[c["name"]] = c["value"]

                try:
                    js_cookies = page.evaluate("document.cookie")
                    if js_cookies:
                        for part in js_cookies.split(";"):
                            part = part.strip()
                            if "=" in part:
                                k, v = part.split("=", 1)
                                k = k.strip()
                                v = v.strip()
                                if k:
                                    result_cookies[k] = v
                except Exception:
                    pass

                cookie_str = "; ".join(f"{k}={v}" for k, v in result_cookies.items())
                logger.info(f"Extracted {len(result_cookies)} cookies from browser session")

                detected_user = request.username
                try:
                    user_el = page.query_selector(".username, .member-name, .profile-name, .user-name, [data-username]")
                    if user_el:
                        detected_user = (user_el.inner_text() or request.username).strip()
                except Exception:
                    pass

                return {"success": True, "cookies": cookie_str, "username": detected_user}
            except Exception as e:
                logger.exception(f"Login error: {e}")
                return {"error": str(e)}
            finally:
                logger.info("Closing browser window...")
                browser.close()
                logger.info("Browser closed.")

    result = await run_sync(_do_login)
    if not result or "error" in result:
        raise HTTPException(status_code=400, detail=(result or {}).get("error", "登录失败"))

    cfg = load_config()
    cfg.jable_session_cookie = result["cookies"]
    cfg.jable_username = result["username"]
    # Also merge into jable_cookie for downstream downloads
    existing = {}
    if cfg.jable_cookie:
        existing.update(AppConfig.parse_cookie_string(cfg.jable_cookie))
    if cfg.jable_session_cookie:
        existing.update(AppConfig.parse_cookie_string(cfg.jable_session_cookie))
    cfg.jable_cookie = "; ".join(f"{k}={v}" for k, v in existing.items())
    save_config(cfg)

    return {
        "status": "ok",
        "message": "登录成功",
        "username": result["username"],
    }


@router.post("/api/jable/logout")
async def jable_logout():
    cfg = load_config()
    cfg.jable_session_cookie = ""
    cfg.jable_username = ""
    save_config(cfg)
    return {"status": "ok"}


@router.post("/api/jable/batch-download")
async def batch_download_codes(
    request: BatchDownloadRequest,
    manager: DownloadManager = Depends(get_download_manager),
):
    cfg = load_config()
    output_dir = (request.output_dir or cfg.output_dir or "").strip()
    if not output_dir:
        raise HTTPException(status_code=400, detail="output_dir is required")

    import os
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    history = manager.history_manager.get_history(10000)
    history_codes = []
    for h in history:
        url = h.get("url", "")
        if "/videos/" in url:
            history_codes.append(url.strip("/").split("/")[-1].lower())

    existing_files = set()
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            existing_files.add(os.path.splitext(f)[0].lower())

    added = 0
    skipped = []
    errors = []
    tasks = []

    for code in request.codes:
        code = code.strip().lower()
        if not code:
            continue
        if code in history_codes:
            skipped.append(code)
            continue
        if code in existing_files:
            skipped.append(code)
            continue
        try:
            res = manager.start_download(f"https://jable.tv/videos/{code}/", output_dir, scrape_after_download=False)
            if res["status"] == "success":
                added += 1
                tasks.append({"code": code, "task_id": res["task_id"]})
                history_codes.append(code)
            else:
                errors.append(f"{code}: {res.get('message', 'unknown')}")
        except Exception as e:
            errors.append(f"{code}: {str(e)}")

    return {"added": added, "skipped": skipped, "errors": errors, "tasks": tasks}