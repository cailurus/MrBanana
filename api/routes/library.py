from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from mr_banana.utils.config import load_config

router = APIRouter()


def _get_library_root() -> Path | None:
    cfg = load_config()
    # Priority: player_root_dir > scrape_output_dir (播放器优先)
    root_dir = str(getattr(cfg, "player_root_dir", "") or "").strip() or str(getattr(cfg, "scrape_output_dir", "") or "").strip()
    if not root_dir:
        return None
    root = Path(os.path.expanduser(root_dir))
    if not root.exists() or not root.is_dir():
        return None
    return root


def _get_all_media_roots() -> list[Path]:
    """Get all possible media root directories (output dir, input dir, player root)."""
    cfg = load_config()
    roots = []
    for attr in ("scrape_output_dir", "scrape_input_dir", "player_root_dir"):
        dir_str = str(getattr(cfg, attr, "") or "").strip()
        if not dir_str:
            continue
        root = Path(os.path.expanduser(dir_str))
        if root.exists() and root.is_dir() and root not in roots:
            roots.append(root)
    return roots


def _safe_join_under_root(root: Path, rel: str) -> Path:
    root_resolved = root.resolve()
    rel_clean = unquote(str(rel or "")).lstrip("/\\")
    p = (root_resolved / rel_clean).resolve()
    if not str(p).startswith(str(root_resolved) + os.sep) and p != root_resolved:
        raise HTTPException(status_code=400, detail="Invalid path")
    return p


def _first_text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    child = el.find(path)
    if child is None or child.text is None:
        return None
    s = str(child.text).strip()
    return s or None


def _parse_movie_nfo(nfo_path: Path) -> dict:
    try:
        xml = nfo_path.read_bytes()
        root = ET.fromstring(xml)
    except Exception:
        return {}

    title = _first_text(root, "title")
    code = _first_text(root, "id")
    url = _first_text(root, "website")
    plot = _first_text(root, "plot")
    release = _first_text(root, "premiered") or _first_text(root, "releasedate")
    studio = _first_text(root, "studio")

    actors: list[str] = []
    for a in root.findall("actor"):
        name = _first_text(a, "name")
        if name:
            actors.append(name)

    tags: list[str] = []
    for g in root.findall("genre"):
        if g.text and str(g.text).strip():
            tags.append(str(g.text).strip())

    poster_name = _first_text(root, "poster") or _first_text(root, "cover")
    fanart_name = None
    fanart_el = root.find("fanart")
    if fanart_el is not None:
        fanart_name = _first_text(fanart_el, "thumb")

    return {
        "title": title,
        "code": code,
        "url": url,
        "plot": plot,
        "release": release,
        "studio": studio,
        "actors": actors,
        "tags": tags,
        "_poster_name": poster_name,
        "_fanart_name": fanart_name,
    }


@router.get("/api/library/items")
async def list_library_items(limit: int = 200):
    root = _get_library_root()
    if root is None:
        return []

    items: list[dict] = []
    max_items = max(1, min(int(limit or 200), 500))

    nfos: list[Path] = []
    try:
        for p in root.rglob("*.nfo"):
            if p.is_file():
                nfos.append(p)
    except Exception:
        return []

    nfos.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

    for nfo in nfos:
        if len(items) >= max_items:
            break
        meta = _parse_movie_nfo(nfo)
        if not meta:
            continue

        video_path = None
        try:
            for cand in nfo.parent.iterdir():
                if not cand.is_file():
                    continue
                if cand.suffix.lower() not in video_exts:
                    continue
                if cand.stem == nfo.stem:
                    video_path = cand
                    break
        except Exception:
            video_path = None

        def asset_url(filename: str | None) -> str | None:
            if not filename:
                return None
            try:
                asset_path = (nfo.parent / filename)
                rel = str(asset_path.relative_to(root))
            except Exception:
                return None
            return f"/api/library/file?rel={quote(rel)}"

        poster_url = asset_url(meta.get("_poster_name"))
        fanart_url = asset_url(meta.get("_fanart_name"))

        preview_urls: list[str] = []
        try:
            for p in sorted(nfo.parent.glob(f"{nfo.stem}-preview-*.*")):
                if len(preview_urls) >= 12:
                    break
                if not p.is_file():
                    continue
                u = asset_url(p.name)
                if u:
                    preview_urls.append(u)
        except Exception:
            preview_urls = []

        video_rel = None
        if video_path is not None:
            try:
                video_rel = str(video_path.relative_to(root))
            except Exception:
                video_rel = None

        items.append(
            {
                "video_rel": video_rel,
                "title": meta.get("title") or (video_path.stem if video_path else nfo.stem),
                "code": meta.get("code") or nfo.stem,
                "url": meta.get("url"),
                "release": meta.get("release"),
                "studio": meta.get("studio"),
                "plot": meta.get("plot"),
                "actors": meta.get("actors") or [],
                "tags": meta.get("tags") or [],
                "poster_url": poster_url,
                "fanart_url": fanart_url,
                "preview_urls": preview_urls,
            }
        )

    return items


@router.get("/api/library/file")
async def get_library_file(rel: str):
    # Try all possible media roots to find the file
    roots = _get_all_media_roots()
    if not roots:
        raise HTTPException(status_code=404, detail="library root is not configured")

    found_path = None
    for root in roots:
        try:
            p = _safe_join_under_root(root, rel)
            if p.exists() and p.is_file():
                found_path = p
                break
        except HTTPException:
            # Invalid path for this root, try next
            continue

    if found_path is None:
        raise HTTPException(status_code=404, detail="file not found")

    ext = found_path.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=403, detail="file type not allowed")

    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return FileResponse(str(found_path), media_type=media_type)


@router.get("/api/library/video")
async def stream_library_video(rel: str, request: Request):
    # Try all possible media roots to find the file
    roots = _get_all_media_roots()
    if not roots:
        raise HTTPException(status_code=404, detail="library root is not configured")

    p = None
    for root in roots:
        try:
            candidate = _safe_join_under_root(root, rel)
            if candidate.exists() and candidate.is_file():
                p = candidate
                break
        except HTTPException:
            continue

    if p is None:
        raise HTTPException(status_code=404, detail="file not found")

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
    if p.suffix.lower() not in video_exts:
        raise HTTPException(status_code=403, detail="file type not allowed")

    size = p.stat().st_size
    range_header = request.headers.get("range")

    media_type = {
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
    }.get(p.suffix.lower(), "application/octet-stream")

    def iter_file(start: int, end: int, chunk_size: int = 1024 * 1024):
        with p.open("rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    if not range_header:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(size),
        }
        return StreamingResponse(iter_file(0, size - 1), media_type=media_type, headers=headers)

    # Range: bytes=start-end
    try:
        units, rng = range_header.split("=", 1)
        if units.strip().lower() != "bytes":
            raise ValueError("invalid units")
        start_s, end_s = (rng.split("-", 1) + [""])
        start = int(start_s) if start_s.strip() else 0
        end = int(end_s) if end_s.strip() else size - 1
        if start < 0 or end < 0 or start > end or start >= size:
            raise ValueError("invalid range")
        end = min(end, size - 1)
    except Exception:
        raise HTTPException(status_code=416, detail="invalid range")

    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(length),
    }
    return StreamingResponse(iter_file(start, end), status_code=206, media_type=media_type, headers=headers)


@router.get("/api/image-proxy")
async def image_proxy(url: str, referer: str | None = None):
    raw = str(url or "").strip()
    if not raw or len(raw) > 4096:
        raise HTTPException(status_code=400, detail="invalid url")
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raise HTTPException(status_code=400, detail="only http/https urls are allowed")

    try:
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="invalid url")
        default_ref = f"{parsed.scheme}://{parsed.netloc}/"
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="invalid url")

    ref = str(referer or "").strip() or default_ref
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": ref,
    }

    try:
        from curl_cffi import requests as crequests  # type: ignore

        r = crequests.get(raw, timeout=25, verify=False, impersonate="chrome", headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"upstream status {r.status_code}")
        content_type = (r.headers.get("content-type") if hasattr(r, "headers") else None) or "image/jpeg"
        return Response(content=r.content, media_type=str(content_type))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"proxy failed: {e}")
