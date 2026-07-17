"""Inspect jable.tv pagination structure via CDP Chrome."""
import sys, json, time
sys.path.insert(0, '.')
from scripts.mcp_cdp_cookie_server import _get_ws_debugger_urls
import websocket

targets = _get_ws_debugger_urls()
page_targets = [t for t in targets if t.get('type') == 'page' and 'jable.tv' in str(t.get('url',''))]

if not page_targets:
    print("No jable.tv tab found!")
    sys.exit(1)

# Find a tab on the favourites page
fav_target = None
for t in page_targets:
    if 'favourites' in str(t.get('url','')) or 'fav' in str(t.get('url','')):
        fav_target = t
        break
if not fav_target:
    fav_target = page_targets[0]

ws_url = fav_target.get('webSocketDebuggerUrl')
print(f"Connected to: {fav_target.get('title','')[:80]}")

ws = websocket.create_connection(ws_url, timeout=10, header={"Origin": "http://127.0.0.1:9222"})

msg_counter = [0]
def cdp(method, params=None):
    msg_counter[0] += 1
    msg_id = msg_counter[0]
    payload = json.dumps({"id": msg_id, "method": method, "params": params or {}})
    ws.send(payload)
    while True:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get('id') == msg_id:
            if 'error' in msg:
                return None, msg['error']
            return msg.get('result', {}), None

cdp("Runtime.enable")

# Run JavaScript to inspect the page structure
js_code = """
(function() {
    var result = {};
    
    // Check URL
    result.url = window.location.href;
    result.hash = window.location.hash;
    
    // Look for any pagination elements
    var paginations = [];
    document.querySelectorAll('[class*="pagin"], [class*="pager"], [class*="page"], nav').forEach(function(el) {
        if (el.offsetParent !== null) {  // visible
            paginations.push({
                tag: el.tagName,
                class: el.className,
                id: el.id,
                innerHTML_preview: el.innerHTML.substring(0, 500)
            });
        }
    });
    result.paginations = paginations;
    
    // Look for any link or button with numbers
    var pageLinks = [];
    document.querySelectorAll('a, button, span[role="button"]').forEach(function(el) {
        var text = el.innerText.trim();
        var cls = el.className || '';
        // Check if it looks like a page number
        if (/^[0-9]+$/.test(text) && el.offsetParent !== null) {
            pageLinks.push({
                tag: el.tagName,
                text: text,
                class: cls,
                href: el.getAttribute('href') || '',
                dataAttrs: Object.keys(el.dataset).join(',')
            });
        }
        // Check for next/prev
        if (/next|prev|more|›|»|load/i.test(text) && el.offsetParent !== null) {
            pageLinks.push({
                tag: el.tagName,
                text: text,
                class: cls,
                href: el.getAttribute('href') || '',
                dataAttrs: Object.keys(el.dataset).join(',')
            });
        }
    });
    result.pageLinks = pageLinks.slice(0, 20);
    
    // Check for network/XHR patterns - look for potential API endpoints embedded in page
    var scripts = [];
    document.querySelectorAll('script').forEach(function(s) {
        var src = s.src || '';
        if (src && (src.includes('favourite') || src.includes('list') || src.includes('page') || src.includes('ajax'))) {
            scripts.push(src);
        }
    });
    result.relevantScripts = scripts.slice(0, 10);
    
    // Check if there's a scroll-based load
    result.scrollHeight = document.documentElement.scrollHeight;
    result.viewportHeight = window.innerHeight;
    result.hasScroll = document.documentElement.scrollHeight > window.innerHeight;
    
    // Check for ajax/list URL patterns in network
    result.allText_pagination_related = [];
    document.querySelectorAll('[data-url], [data-ajax], [data-source], [data-endpoint]').forEach(function(el) {
        for (var key in el.dataset) {
            var val = el.dataset[key];
            if (val && typeof val === 'string' && val.includes('jable.tv')) {
                result.allText_pagination_related.push(key + '=' + val.substring(0, 200));
            }
        }
    });
    
    // Check localStorage for any list endpoints
    try {
        result.localStorage_pagination = localStorage.getItem('pagination') || localStorage.getItem('listData') || null;
    } catch(e) {}
    
    return JSON.stringify(result);
})()
"""

result, err = cdp("Runtime.evaluate", {
    "expression": js_code,
    "returnByValue": True
})

if err:
    print(f"CDP Error: {err}")
else:
    val = result.get('result', {}).get('value', '')
    if isinstance(val, str) and val:
        data = json.loads(val)
        print("\n=== PAGE INSPECTION ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))

ws.close()