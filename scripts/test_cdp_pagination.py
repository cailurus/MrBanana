"""Test CDP-based pagination for jable.tv lists."""
import sys, json, time, re
sys.path.insert(0, '.')
from scripts.mcp_cdp_cookie_server import _get_ws_debugger_urls
import websocket

targets = _get_ws_debugger_urls()
page_targets = [t for t in targets if t.get('type') == 'page' and 'jable.tv' in str(t.get('url',''))]

if not page_targets:
    print("No jable.tv tab found. Open https://jable.tv/my/favourites/videos/ in Chrome CDP first.")
    sys.exit(1)

target = page_targets[0]
ws_url = target.get('webSocketDebuggerUrl')
print(f"Connecting to: {target.get('title','')[:60]}")

ws = websocket.create_connection(ws_url, timeout=10, header={"Origin": "http://127.0.0.1:9222"})

def cdp_send(method, params=None):
    msg_id = int(time.time() * 1000) % 100000
    payload = json.dumps({"id": msg_id, "method": method, "params": params or {}})
    ws.send(payload)
    while True:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get('id') == msg_id:
            if 'error' in msg:
                return None, msg['error']
            return msg.get('result', {}), None

# Enable Runtime domain
cdp_send("Runtime.enable")

# First, check current page URL and pagination structure
result, err = cdp_send("Runtime.evaluate", {
    "expression": """
    (function() {
        // Check pagination structure
        const pagination = document.querySelector('.pagination, .pagination-area, .pager, nav[aria-label]');
        let pageLinks = [];
        if (pagination) {
            const links = pagination.querySelectorAll('a, button, [role="button"]');
            links.forEach(l => {
                pageLinks.push({text: l.innerText.trim(), href: l.getAttribute('href') || '', class: l.className});
            });
        }
        
        // Check if there's a "load more" button
        const loadMore = document.querySelector('[class*="load-more"], [class*="loadmore"], [class*="more"], button:has-text("more"), button:has-text("load")');
        
        // Get all video cards
        const cards = document.querySelectorAll('.video-img-box, [class*="video-card"], [class*="video-item"]');
        
        // Check for AJAX/infinite scroll indicators
        const hasInfiniteScroll = !!document.querySelector('[data-page], [data-offset], .infinite-scroll');
        
        return {
            url: window.location.href,
            title: document.title,
            cardCount: cards.length,
            paginationHTML: pagination ? pagination.outerHTML.substring(0, 500) : null,
            pageLinks: pageLinks,
            hasLoadMore: !!loadMore,
            hasInfiniteScroll: hasInfiniteScroll,
            hash: window.location.hash,
        };
    })()
    """,
    "returnByValue": True
})

print("\n=== Page Analysis ===")
print(json.dumps(result.get('result', {}).get('value', {}), indent=2, ensure_ascii=False))

ws.close()