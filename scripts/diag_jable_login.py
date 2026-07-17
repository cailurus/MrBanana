"""Diagnose jable.tv login page structure"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patchright.sync_api import sync_playwright
from mr_banana.utils.config import load_config, AppConfig

cfg = load_config()

# Build CF cookies
cf_cookies = {}
if cfg.jable_cookie:
    cf_cookies = AppConfig.parse_cookie_string(cfg.jable_cookie)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox", "--disable-setuid-sandbox", "--window-size=1280,720"])
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    
    # Inject CF cookies
    if cf_cookies:
        cookie_list = [{"name": k, "value": v, "domain": "jable.tv", "path": "/", "httpOnly": False, "secure": True, "sameSite": "Lax"} for k, v in cf_cookies.items()]
        try:
            context.add_cookies(cookie_list)
            print(f"Injected {len(cf_cookies)} CF cookies: {list(cf_cookies.keys())}")
        except Exception as e:
            print(f"Failed to inject cookies (not on jable.tv yet): {e}")
    
    page = context.new_page()
    
    print("=== Navigating to https://jable.tv/login/ ===")
    resp = page.goto("https://jable.tv/login/", wait_until="domcontentloaded", timeout=30000)
    print(f"HTTP Status: {resp.status if resp else 'N/A'}")
    print(f"Final URL: {page.url}")
    print(f"Page title: {page.title()}")
    
    # Check if cloudflare challenge present
    content_snippet = page.content()[:2000]
    has_cf = "cf-challenge" in content_snippet.lower() or "just a moment" in content_snippet.lower() or "checking your browser" in content_snippet.lower()
    print(f"Cloudflare challenge detected: {has_cf}")
    
    # Wait a bit
    import time
    time.sleep(3)
    
    print(f"\n=== Page after wait ===")
    print(f"URL: {page.url}")
    print(f"Title: {page.title()}")
    
    # Try to take screenshot
    try:
        page.screenshot(path="scripts/login_page.png")
        print("Screenshot saved to scripts/login_page.png")
    except Exception as e:
        print(f"Screenshot failed: {e}")
    
    # Print all input elements
    print("\n=== Input elements found ===")
    inputs = page.query_selector_all("input")
    for inp in inputs:
        name = inp.get_attribute("name") or ""
        type_ = inp.get_attribute("type") or ""
        id_ = inp.get_attribute("id") or ""
        placeholder = inp.get_attribute("placeholder") or ""
        classes = inp.get_attribute("class") or ""
        print(f"  <input name='{name}' type='{type_}' id='{id_}' placeholder='{placeholder}' class='{classes[:80]}'>")
    
    if not inputs:
        print("  NO INPUT ELEMENTS FOUND!")
    
    # Print all forms
    print("\n=== Form elements ===")
    forms = page.query_selector_all("form")
    for f in forms:
        action = f.get_attribute("action") or ""
        method = f.get_attribute("method") or ""
        print(f"  <form action='{action}' method='{method}'>")
        inner = f.inner_html()[:500]
        print(f"    inner: {inner[:300]}")
    
    # Print all buttons
    print("\n=== Button elements ===")
    for btn in page.query_selector_all("button"):
        text = btn.inner_text() or ""
        type_ = btn.get_attribute("type") or ""
        print(f"  <button type='{type_}'>'{text[:60]}'</button>")
    
    # Full HTML snippet (first 3000 chars)
    html = page.content()
    print(f"\n=== HTML length: {len(html)} ===")
    print(html[:3000])
    
    print("\n=== DONE ===")
    browser.close()