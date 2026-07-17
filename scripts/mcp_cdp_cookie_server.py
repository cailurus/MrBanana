#!/usr/bin/env python3
"""
CDP Cookie Extractor MCP Server

Connects to a running Chrome instance via Chrome DevTools Protocol (CDP)
and extracts cookies for specified domains. Designed for Mr. Banana's jable.tv
integration - extract Cloudflare cf_clearance and session cookies from an
already-logged-in browser session.

Requirements:
    pip install mcp websocket-client

Usage:
    Start Chrome with: chrome --remote-debugging-port=9222
    Then this MCP server will expose tools to extract cookies.
"""

import json
import sys
import logging
from typing import Any

import websocket

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Logging (stderr so it doesn't interfere with MCP stdio protocol)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [CDP-MCP] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("cdp-cookie-mcp")

# ---------------------------------------------------------------------------
# CDP Client
# ---------------------------------------------------------------------------

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222


def _get_ws_debugger_urls() -> list[dict]:
    """Fetch the list of debuggable pages/targets from Chrome's HTTP endpoint."""
    import http.client

    conn = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
    try:
        conn.request("GET", "/json")
        resp = conn.getresponse()
        data = resp.read().decode("utf-8")
        return json.loads(data)
    finally:
        conn.close()


def _cdp_send(ws: websocket.WebSocket, method: str, params: dict | None = None) -> dict:
    """Send a CDP command and wait for the result."""
    msg_id = int(id(ws) % 100000)
    payload = json.dumps({"id": msg_id, "method": method, "params": params or {}})
    log.debug("CDP send: %s", method)
    ws.send(payload)

    timeout = 10
    started = 0
    import time
    while True:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            time.sleep(0.1)
            started += 1
            if started > 100:  # 10 seconds
                raise TimeoutError(f"CDP timeout waiting for {method}")
            continue

        msg = json.loads(raw)
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RuntimeError(f"CDP error: {msg['error']}")
            return msg.get("result", {})
        # Otherwise might be an event, continue reading.


def extract_cookies_for_domain(domain: str = "jable.tv") -> list[dict[str, Any]]:
    """
    Connect to the first available page target in Chrome via CDP
    and extract all cookies for the specified domain.
    Does NOT navigate away from the current page to avoid disrupting the user.
    """
    targets = _get_ws_debugger_urls()

    # Find a page target that is on or related to the target domain
    # Prefer pages that already have the target domain in their URL
    page_targets = [t for t in targets if t.get("type") == "page"]
    if not page_targets:
        raise RuntimeError(
            "No page targets found. Make sure Chrome is running with "
            "a jable.tv tab open. Start Chrome with: chrome --remote-debugging-port=9222 --remote-allow-origins=*"
        )

    # Prefer a page that's already on the target domain
    domain_target = None
    for t in page_targets:
        if domain in str(t.get("url", "")):
            domain_target = t
            break

    # Fall back to first page target
    if domain_target is None:
        domain_target = page_targets[0]
        log.warning("No tab found on %s, using first available page: %s", domain, domain_target.get("url"))

    ws_url = domain_target.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("No WebSocket debugger URL found on page target")

    log.info("Connecting to CDP at %s (page: %s)", ws_url, domain_target.get("title", "unknown"))

    # Add Origin header to bypass Chrome's origin check
    ws = websocket.create_connection(
        ws_url,
        timeout=10,
        header={"Origin": "http://127.0.0.1:9222"},
    )

    try:
        # Enable Network domain to access cookies
        _cdp_send(ws, "Network.enable")

        # Get cookies for all URLs (not just the current page's URL)
        # This gets cookies that are scoped to the domain
        result = _cdp_send(ws, "Network.getCookies", {
            "urls": [f"https://{domain}/", f"https://www.{domain}/"]
        })

        all_cookies = result.get("cookies", [])

        # If no cookies returned with URL filter, try without filter
        if not all_cookies:
            log.info("No cookies found with URL filter, trying unfiltered...")
            result = _cdp_send(ws, "Network.getAllCookies")
            all_cookies = result.get("cookies", [])

        # Filter for target domain
        domain_cookies = [
            c for c in all_cookies
            if domain in str(c.get("domain", ""))
        ]

        log.info("Found %d cookies for domain %s (out of %d total)",
                 len(domain_cookies), domain, len(all_cookies))

        return domain_cookies

    finally:
        ws.close()


def format_for_mr_banana(cookies: list[dict]) -> dict[str, str]:
    """Convert CDP cookie list to Mr. Banana's config format.

    Returns:
        {
            "cookie_string": "cf_clearance=xxx; session=yyy",
            "jable_cookie": "cf_clearance=xxx; session=yyy",
            "cookies": {"cf_clearance": "xxx", ...},
            "key_cookies": {"cf_clearance": "...", "PHPSESSID": "..."},
        }
    """
    cookie_dict: dict[str, str] = {}
    for c in cookies:
        name = c.get("name", "")
        value = c.get("value", "")
        if name:
            cookie_dict[name] = value

    # Build cookie header string
    cookie_string = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())

    # Identify key cookies
    key_cookies = {}
    important_keys = ["cf_clearance", "__cf_bm", "PHPSESSID", "session", "remember_web_xxx"]
    for k in important_keys:
        if k in cookie_dict:
            key_cookies[k] = cookie_dict[k]
    # Also include any cookie with 'cf_' prefix
    for k, v in cookie_dict.items():
        if k.startswith("cf_") and k not in key_cookies:
            key_cookies[k] = v

    return {
        "cookie_string": cookie_string,
        "jable_cookie": cookie_string,
        "cookies": cookie_dict,
        "key_cookies": key_cookies,
        "total_cookie_count": len(cookie_dict),
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("cdp-cookie-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="extract_cookies",
            description=(
                "Connect to a running Chrome browser via Chrome DevTools Protocol (CDP) "
                "and extract all cookies for a specified domain. "
                "Chrome must be started with --remote-debugging-port=9222. "
                "Use this to get Cloudflare clearance cookies (cf_clearance) and session cookies "
                "from an already-logged-in browser session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to extract cookies for (e.g. jable.tv, javdb.com)",
                        "default": "jable.tv",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="extract_jable_cookies",
            description=(
                "Extract jable.tv cookies from a running Chrome browser and format them "
                "for direct use in Mr. Banana's config. Returns the cookie string ready to "
                "paste into the jable_cookie config field. "
                "Chrome must be started with --remote-debugging-port=9222 and have a "
                "logged-in jable.tv tab."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "extract_cookies":
            domain = str(arguments.get("domain", "jable.tv")).strip() or "jable.tv"
            cookies = extract_cookies_for_domain(domain)
            formatted = format_for_mr_banana(cookies)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "domain": domain,
                    **formatted,
                    "raw_cookies": cookies,
                }, indent=2, ensure_ascii=False),
            )]

        elif name == "extract_jable_cookies":
            cookies = extract_cookies_for_domain("jable.tv")
            formatted = format_for_mr_banana(cookies)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "domain": "jable.tv",
                    "mr_banana_config": {
                        "jable_cookie": formatted["jable_cookie"],
                        "instructions": (
                            "Copy the jable_cookie value above and paste it into "
                            "Mr. Banana's Download Settings → Jable Cookie field. "
                            "This will allow Mr. Banana to bypass Cloudflare without "
                            "launching a browser."
                        ),
                    },
                    "key_cookies_found": formatted["key_cookies"],
                    "total_cookies": formatted["total_cookie_count"],
                }, indent=2, ensure_ascii=False),
            )]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": f"Unknown tool: {name}"}),
            )]

    except RuntimeError as e:
        msg = str(e)
        log.exception("Runtime error in tool %s", name)
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": msg,
                "hint": (
                    "Make sure Chrome is running with --remote-debugging-port=9222 "
                    "and has a tab open on the target domain. "
                    "Start Chrome: chrome --remote-debugging-port=9222"
                ),
            }, indent=2, ensure_ascii=False),
        )]
    except Exception as e:
        log.exception("Unexpected error in tool %s", name)
        return [TextContent(
            type="text",
            text=json.dumps({"status": "error", "message": str(e)}, indent=2),
        )]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())