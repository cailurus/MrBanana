"""Test: click through jable.tv pagination via CDP and verify each page has different content."""
import sys, json, time
sys.path.insert(0, '.')
from scripts.mcp_cdp_cookie_server import _get_ws_debugger_urls
import websocket

targets = _get_ws_debugger_urls()
page_targets = [t for t in targets if t.get('type') == 'page' and 'jable.tv' in str(t.get('url',''))]
for t in page_targets:
    print(f"Tab: url={t.get('url','')[:80]}  type={t.get('type')}")

# Connect to jable.tv tab directly and run JS to click through pages
fav_target = None
for t in page_targets:
    if 'favourites' in str(t.get('url','')):
        fav_target = t
        break
if not fav_target:
    fav_target = page_targets[0]

ws_url = fav_target.get('webSocketDebuggerUrl')
ws = websocket.create_connection(ws_url, timeout=10, header={"Origin": "http://127.0.0.1:9222"})
msg_id = [0]
def cdp(m, p=None):
    msg_id[0] += 1
    mid = msg_id[0]
    ws.send(json.dumps({"id": mid, "method": m, "params": p or {}}))
    while True:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get('id') == mid:
            return msg.get('result', {}), msg.get('error')

cdp("Runtime.enable")

# First, navigate to favourites page and wait for load
js_nav = """
(async function() {
    var url = 'https://jable.tv/my/favourites/videos/';
    if (window.location.href !== url) {
        window.location.href = url;
        await new Promise(r => setTimeout(r, 3000));
    }
    return {url: window.location.href, title: document.title};
})()
"""
r, e = cdp("Runtime.evaluate", {"expression": js_nav, "returnByValue": True, "awaitPromise": True})
print(f"NAV: {json.dumps(r.get('result',{}).get('value',''), indent=2)[:200]}")

time.sleep(3)

# Try clicking page 2 using JS directly (avoids Playwright handle staleness)
for page_num in range(2, 5):
    js_click = f"""
    (function() {{
        // Find all page links and click the one matching page {page_num}
        var links = document.querySelectorAll('ul.pagination li.page-item a.page-link');
        var found = null;
        for (var i = 0; i < links.length; i++) {{
            if (links[i].innerText.trim() === '{str(page_num).zfill(2)}') {{
                found = links[i];
                break;
            }}
        }}
        if (found) {{
            found.click();
            return 'clicked page {page_num}';
        }}
        return 'NOT FOUND page {page_num}';
    }})()
    """
    r, e = cdp("Runtime.evaluate", {"expression": js_click, "returnByValue": True})
    print(f"CLICK page {page_num}: {r.get('result',{}).get('value','')}")
    time.sleep(3)
    
    # Verify what codes are on the page now
    js_codes = """
    (function() {
        var codes = [];
        document.querySelectorAll('.video-img-box a[href*="/videos/"]').forEach(function(a) {
            var href = a.getAttribute('href');
            var code = href.split('/').filter(Boolean).pop();
            if (code && code !== 'videos') codes.push(code);
        });
        return codes.slice(0, 5);
    })()
    """
    r, e = cdp("Runtime.evaluate", {"expression": js_codes, "returnByValue": True})
    print(f"  Sample codes: {r.get('result',{}).get('value','')}")

ws.close()