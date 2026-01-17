"""
Search API - Search for video metadata by code from JavDB and check Jable.tv availability
"""
from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from curl_cffi import requests

from mr_banana.scraper.crawlers.javdb import JavdbCrawler, JavdbConfig
from mr_banana.utils.config import load_config

router = APIRouter()


class SearchRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Video code to search for")


class MagnetLink(BaseModel):
    url: str
    name: str
    size: str
    is_hd: bool
    has_subtitle: bool


class SearchResult(BaseModel):
    found: bool
    code: str
    # JavDB metadata
    javdb_found: bool = False
    title: str | None = None
    cover_url: str | None = None
    poster_url: str | None = None
    actors: list[str] = []
    tags: list[str] = []
    release: str | None = None
    runtime: str | None = None
    studio: str | None = None
    publisher: str | None = None
    series: str | None = None
    directors: list[str] = []
    rating: str | None = None
    plot: str | None = None
    preview_urls: list[str] = []
    trailer_url: str | None = None
    javdb_url: str | None = None
    magnet_links: list[MagnetLink] = []
    # Jable.tv availability
    jable_available: bool = False
    jable_url: str | None = None


def normalize_code(code: str) -> str:
    """Normalize video code to standard format."""
    code = code.strip().upper()
    # Remove common prefixes/suffixes
    code = re.sub(r'^(HD|SD|FHD|4K)[-_]?', '', code, flags=re.IGNORECASE)
    code = re.sub(r'[-_]?(HD|SD|FHD|4K|UNCENSORED|UC)$', '', code, flags=re.IGNORECASE)
    # Normalize separator
    code = re.sub(r'[-_\s]+', '-', code)
    return code


def check_jable_availability(code: str, proxy_url: str | None = None) -> tuple[bool, str | None]:
    """Check if a video is available on Jable.tv.
    
    Also checks for -c suffix variants (e.g., ssni-369-c).
    
    Returns:
        Tuple of (is_available, jable_url)
    """
    # Try multiple URL variants: original and -c suffix
    code_lower = code.lower()
    url_variants = [
        f"https://jable.tv/videos/{code_lower}/",
        f"https://jable.tv/videos/{code_lower}-c/",
    ]
    
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        
        for jable_url in url_variants:
            # Use HEAD request first to check availability (faster)
            response = requests.head(
                jable_url,
                headers=headers,
                timeout=10,
                verify=False,
                allow_redirects=True,
                impersonate="chrome",
                proxies=proxies,
            )
            
            # If HEAD returns 200, the video exists
            if response.status_code == 200:
                return True, jable_url
            
            # Some servers don't support HEAD, try GET
            if response.status_code in (405, 403):
                response = requests.get(
                    jable_url,
                    headers=headers,
                    timeout=10,
                    verify=False,
                    impersonate="chrome",
                    proxies=proxies,
                )
                if response.status_code == 200:
                    # Check if it's not a 404 page or redirect to home
                    content = response.text[:2000] if response.text else ""
                    if "404" not in content and "找不到" not in content and "not found" not in content.lower():
                        return True, jable_url
        
        return False, None
    except Exception:
        return False, None


@router.get("/api/search/{code}")
async def search_by_code(code: str):
    """Search for video metadata by code."""
    if not code or len(code) > 50:
        raise HTTPException(status_code=400, detail="Invalid code")
    
    normalized_code = normalize_code(code)
    if not normalized_code:
        raise HTTPException(status_code=400, detail="Invalid code format")
    
    # Load config for proxy settings
    cfg = load_config()
    proxy_url = None
    if getattr(cfg, "scrape_use_proxy", False):
        proxy_url = getattr(cfg, "scrape_proxy_url", "") or None
    
    result = SearchResult(
        found=False,
        code=normalized_code,
    )
    
    # Search JavDB
    try:
        javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
        crawler = JavdbCrawler(cfg=javdb_cfg)
        crawl_result = crawler.search_by_code(normalized_code)
        
        if crawl_result and crawl_result.data:
            data = crawl_result.data
            result.javdb_found = True
            result.found = True
            result.title = crawl_result.title
            result.cover_url = data.get("cover_url")
            result.poster_url = data.get("poster_url")
            result.actors = data.get("actors", [])
            result.tags = data.get("tags", [])
            result.release = data.get("release")
            result.runtime = data.get("runtime")
            result.studio = data.get("studio")
            result.publisher = data.get("publisher")
            result.series = data.get("series")
            result.directors = data.get("directors", [])
            result.rating = data.get("rating")
            result.plot = data.get("plot")
            result.preview_urls = data.get("preview_urls", [])
            result.trailer_url = data.get("trailer_url")
            result.javdb_url = crawl_result.original_url
            
            # Process magnet links
            magnet_data = data.get("magnet_links", [])
            result.magnet_links = [
                MagnetLink(
                    url=m.get("url", ""),
                    name=m.get("name", normalized_code),
                    size=m.get("size", ""),
                    is_hd=m.get("is_hd", False),
                    has_subtitle=m.get("has_subtitle", False),
                )
                for m in magnet_data
                if m.get("url")
            ]
    except Exception as e:
        # Log error but continue to check Jable
        print(f"JavDB search error: {e}")
    
    # Check Jable.tv availability
    try:
        jable_available, jable_url = check_jable_availability(normalized_code, proxy_url)
        result.jable_available = jable_available
        result.jable_url = jable_url
        if jable_available:
            result.found = True
    except Exception as e:
        print(f"Jable check error: {e}")
    
    return result


@router.post("/api/search")
async def search_by_code_post(request: SearchRequest):
    """Search for video metadata by code (POST method)."""
    return await search_by_code(request.code)
