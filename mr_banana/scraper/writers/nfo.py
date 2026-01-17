from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from typing import Callable
from io import BytesIO

from curl_cffi import requests

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from ..types import MediaInfo, CrawlResult

from mr_banana.utils.hls import HLSDownloader
from mr_banana.utils.network import NetworkHandler


@dataclass
class NfoWriteOptions:
    write_nfo: bool = True
    # If provided, only fields in this set will be written.
    # Supported: title, originaltitle, id, website, plot, release, studio, actors, tags, runtime, resolution, artwork
    nfo_fields: set[str] | None = None

    download_poster: bool = True
    download_fanart: bool = True
    download_previews: bool = False
    download_trailer: bool = False
    preview_limit: int = 8

    # Optional proxy for artwork downloads
    proxy_url: str | None = None

    # Optional logger for download diagnostics
    log_fn: Callable[[str], None] | None = None


def _guess_file_ext(url: str, fallback: str = ".mp4") -> str:
    try:
        path = urlparse(url).path
        ext = Path(path).suffix.lower()
        if ext:
            return ext
    except Exception:
        pass
    return fallback


def _download_file(
    url: str,
    dest: Path,
    max_bytes: int,
    *,
    proxy_url: str | None = None,
    headers: dict[str, str] | None = None,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    try:
        proxies = None
        if proxy_url:
            pu = str(proxy_url).strip()
            if pu:
                proxies = {"http": pu, "https": pu}
        r = requests.get(
            url,
            timeout=60,
            verify=False,
            impersonate="chrome",
            proxies=proxies,
            headers=headers or {},
        )
        if r.status_code != 200:
            if log_fn:
                log_fn(f"trailer download failed: {r.status_code} {url}")
            return False
        content = getattr(r, "content", b"")
        if content is None:
            return False
        if len(content) > max_bytes:
            if log_fn:
                log_fn(f"trailer too large ({len(content)} bytes), skip: {url}")
            return False
        dest.write_bytes(content)
        if log_fn:
            log_fn(f"trailer downloaded: {dest.name} ({len(content)} bytes) <- {url}")
        return True
    except Exception:
        if log_fn:
            log_fn(f"trailer download error: {url}")
        return False


def _download_hls(
    m3u8_url: str,
    dest: Path,
    *,
    proxy_url: str | None = None,
    headers: dict[str, str] | None = None,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    try:
        proxies = None
        if proxy_url:
            pu = str(proxy_url).strip()
            if pu:
                proxies = {"http": pu, "https": pu}

        net = NetworkHandler(timeout=60, proxies=proxies)
        dl = HLSDownloader(net)
        ok = dl.download(m3u8_url, str(dest), headers=headers)
        if log_fn:
            log_fn(f"trailer hls {'downloaded' if ok else 'failed'}: {dest.name} <- {m3u8_url}")
        return bool(ok)
    except Exception:
        if log_fn:
            log_fn(f"trailer hls download error: {m3u8_url}")
        return False


def _text_el(parent: ET.Element, tag: str, text: str | None):
    el = ET.SubElement(parent, tag)
    if text:
        el.text = text
    return el


def _guess_image_ext(url: str) -> str:
    try:
        path = urlparse(url).path
        ext = Path(path).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            return ext
    except Exception:
        pass
    return ".jpg"


def _download_image(
    url: str,
    dest: Path,
    *,
    proxy_url: str | None = None,
    headers: dict[str, str] | None = None,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    try:
        proxies = None
        if proxy_url:
            pu = str(proxy_url).strip()
            if pu:
                proxies = {"http": pu, "https": pu}
        r = requests.get(
            url,
            timeout=25,
            verify=False,
            impersonate="chrome",
            proxies=proxies,
            headers=headers or {},
        )
        final_url = None
        try:
            final_url = str(getattr(r, "url", "") or "")
        except Exception:
            final_url = None

        # DMM often redirects missing assets to placeholder images (now_printing / noimage).
        # Treat those as a failed download to avoid saving blank previews.
        if final_url:
            low = final_url.lower()
            if "now_printing" in low or "/noimage/" in low:
                if log_fn:
                    log_fn(f"artwork placeholder image, skip: {final_url} <- {url}")
                try:
                    if dest.exists():
                        dest.unlink()
                except Exception:
                    pass
                return False
        if r.status_code != 200:
            if log_fn:
                log_fn(f"artwork download failed: {r.status_code} {url}")
            return False
        dest.write_bytes(r.content)
        if log_fn:
            log_fn(f"artwork downloaded: {dest.name} ({len(r.content)} bytes) <- {url}")
        return True
    except Exception:
        if log_fn:
            log_fn(f"artwork download error: {url}")
        return False


def _crop_poster_from_fanart(
    fanart_path: Path,
    poster_path: Path,
    *,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    """从 fanart 裁剪右边 47.5% 作为 poster。
    
    Fanart 是影碟完整封面：左边背面(47.5%) + 中封(5%) + 右边正面(47.5%)
    我们裁剪右边的正面图作为 poster。
    """
    if not HAS_PIL:
        if log_fn:
            log_fn("PIL not available, skip poster cropping from fanart")
        return False
    
    try:
        with Image.open(fanart_path) as img:
            width, height = img.size
            # 裁剪右边 47.5% (52.5% 位置开始)
            crop_start_x = int(width * 0.525)
            cropped = img.crop((crop_start_x, 0, width, height))
            
            # 保存为 JPEG，质量 95
            if cropped.mode in ('RGBA', 'P'):
                cropped = cropped.convert('RGB')
            cropped.save(poster_path, 'JPEG', quality=95)
            
            if log_fn:
                log_fn(f"poster cropped from fanart: {poster_path.name} ({cropped.size[0]}x{cropped.size[1]})")
            return True
    except Exception as e:
        if log_fn:
            log_fn(f"poster crop from fanart failed: {e}")
        return False


def write_nfo(video_path: Path, media: MediaInfo, meta: CrawlResult, options: NfoWriteOptions | None = None) -> Path | None:
    """Write a Kodi/Emby-friendly movie NFO next to the video file.

    Also downloads artwork (poster/fanart/previews) when URLs are available.
    """
    opts = options or NfoWriteOptions()
    emit = opts.log_fn
    include = set(opts.nfo_fields) if opts.nfo_fields else {
        "title",
        "originaltitle",
        "id",
        "website",
        "plot",
        "release",
        "studio",
        "actors",
        "tags",
        "runtime",
        "resolution",
        "artwork",
    }

    root = ET.Element("movie")

    if "title" in include:
        _text_el(root, "title", meta.title or video_path.stem)
    if "originaltitle" in include:
        scraped_original = None
        try:
            if meta.data and isinstance(meta.data.get("originaltitle"), str):
                scraped_original = str(meta.data.get("originaltitle") or "").strip() or None
        except Exception:
            scraped_original = None
        _text_el(root, "originaltitle", scraped_original or meta.title or video_path.stem)
    if "id" in include:
        _text_el(root, "id", meta.external_id)
    if "website" in include:
        _text_el(root, "website", meta.original_url)

    plot = None
    release = None
    studio = None
    actors = []
    tags = []
    cover_url = None
    poster_url = None
    fanart_url = None
    preview_urls = []
    trailer_url = None
    fallback_preview_placeholders = False

    if meta.data:
        plot = meta.data.get("plot")
        release = meta.data.get("release")
        studio = meta.data.get("studio")
        actors = meta.data.get("actors") or []
        tags = meta.data.get("tags") or []
        cover_url = meta.data.get("cover_url")
        poster_url = meta.data.get("poster_url") or meta.data.get("cover_url")
        fanart_url = meta.data.get("fanart_url")
        preview_urls = meta.data.get("preview_urls") or []
        trailer_url = meta.data.get("trailer_url")

    if plot and "plot" in include:
        _text_el(root, "plot", str(plot))
        _text_el(root, "outline", str(plot))

    if release and "release" in include:
        _text_el(root, "premiered", str(release))
        _text_el(root, "releasedate", str(release))

    if studio and "studio" in include:
        _text_el(root, "studio", str(studio))

    if "actors" in include:
        for name in actors:
            if not name:
                continue
            actor_el = ET.SubElement(root, "actor")
            _text_el(actor_el, "name", str(name))
            _text_el(actor_el, "type", "Actor")

    if "tags" in include:
        for t in tags:
            if not t:
                continue
            _text_el(root, "genre", str(t))

    if media.duration_seconds is not None and "runtime" in include:
        runtime_min = int(round(media.duration_seconds / 60.0))
        _text_el(root, "runtime", str(runtime_min))

    if media.width and media.height and "resolution" in include:
        _text_el(root, "resolution", f"{media.width}x{media.height}")

    poster_name = None
    fanart_name = None

    def _referer_for(u: str) -> str | None:
        try:
            if isinstance(meta.original_url, str) and meta.original_url.strip():
                return meta.original_url.strip()
        except Exception:
            pass
        try:
            parsed = urlparse(str(u))
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}/"
        except Exception:
            return None
        return None

    def _headers_for(u: str) -> dict[str, str]:
        h = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        ref = _referer_for(u)
        if ref:
            h["Referer"] = ref

        # JavTrailers (and some redirects like "fenza") may require a JavTrailers referer.
        low = str(u).lower()
        if "javtrailers.com" in low or "fenza" in low:
            h["Referer"] = "https://javtrailers.com/"
        return h

    if fanart_url and opts.download_fanart:
        ext = _guess_image_ext(str(fanart_url))
        fanart_path = video_path.with_name(f"{video_path.stem}-fanart{ext}")
        if emit:
            emit(f"artwork try fanart: {fanart_url}")
        if _download_image(str(fanart_url), fanart_path, proxy_url=opts.proxy_url, headers=_headers_for(str(fanart_url)), log_fn=emit):
            fanart_name = fanart_path.name
            
            # 优先从 fanart 裁剪 poster（更清晰）
            if opts.download_poster:
                poster_path = video_path.with_name(f"{video_path.stem}-poster.jpg")
                if _crop_poster_from_fanart(fanart_path, poster_path, log_fn=emit):
                    poster_name = poster_path.name
                    # 已从 fanart 裁剪，跳过下载 poster_url
                elif poster_url:
                    # 裁剪失败，回退到下载 poster_url
                    ext = _guess_image_ext(str(poster_url))
                    poster_path = video_path.with_name(f"{video_path.stem}-poster{ext}")
                    if emit:
                        emit(f"artwork try poster (fallback): {poster_url}")
                    if _download_image(str(poster_url), poster_path, proxy_url=opts.proxy_url, headers=_headers_for(str(poster_url)), log_fn=emit):
                        poster_name = poster_path.name
    elif poster_url and opts.download_poster:
        # 没有 fanart，直接下载 poster
        ext = _guess_image_ext(str(poster_url))
        poster_path = video_path.with_name(f"{video_path.stem}-poster{ext}")
        if emit:
            emit(f"artwork try poster: {poster_url}")
        if _download_image(str(poster_url), poster_path, proxy_url=opts.proxy_url, headers=_headers_for(str(poster_url)), log_fn=emit):
            poster_name = poster_path.name

    # Best-effort fallback: for some DMM titles, preview URLs follow a predictable pattern.
    # If we didn't scrape any preview_urls but we do have a DMM poster URL, try generating candidates.
    if opts.download_previews and not preview_urls:
        try:
            u = str(cover_url or poster_url or fanart_url or "").strip()
            if u:
                parsed = urlparse(u)
                m = re.search(r"/digital/video/([^/]+)/", parsed.path, flags=re.IGNORECASE)
                if m and parsed.scheme and parsed.netloc:
                    cid = str(m.group(1))
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                # Common DMM sample image pattern: <cid>jp-01.jpg ...
                preview_urls = [f"{origin}/digital/video/{cid}/{cid}jp-{i:02d}.jpg" for i in range(1, 13)]
                if emit:
                    emit(f"artwork fallback previews: generated {len(preview_urls)} candidates from poster_url")

                # If the first candidate resolves to DMM's placeholder image, the pattern is not valid for this title.
                # Drop the whole list to avoid downloading multiple blank placeholders.
                try:
                    test_url = preview_urls[0] if preview_urls else ""
                    if test_url:
                        proxies = None
                        if opts.proxy_url:
                            pu = str(opts.proxy_url).strip()
                            if pu:
                                proxies = {"http": pu, "https": pu}
                        rr = requests.get(
                            test_url,
                            timeout=15,
                            verify=False,
                            impersonate="chrome",
                            proxies=proxies,
                            headers=_headers_for(test_url),
                        )
                        final_url = ""
                        try:
                            final_url = str(getattr(rr, "url", "") or "")
                        except Exception:
                            final_url = ""
                        low = final_url.lower() if final_url else ""
                        if "now_printing" in low or "/noimage/" in low:
                            preview_urls = []
                            fallback_preview_placeholders = True
                            if emit:
                                emit(f"artwork fallback previews: placeholder detected, skip generating previews: {final_url}")
                except Exception:
                    # Keep the generated list; individual downloads will still validate placeholders.
                    pass
        except Exception:
            # keep as empty
            preview_urls = preview_urls or []

    if opts.download_previews and preview_urls:
        try:
            limit = max(0, int(opts.preview_limit or 0))
        except Exception:
            limit = 0
        if limit > 0:
            for i, u in enumerate(preview_urls[:limit], 1):
                try:
                    ext = _guess_image_ext(str(u))
                    p = video_path.with_name(f"{video_path.stem}-preview-{i:02d}{ext}")
                    if emit:
                        emit(f"artwork try preview[{i}]: {u}")
                    _download_image(str(u), p, proxy_url=opts.proxy_url, headers=_headers_for(str(u)), log_fn=emit)
                except Exception:
                    pass
    elif opts.download_previews and emit:
        if fallback_preview_placeholders:
            try:
                # Remove previously saved placeholder previews (typically ~2-3KB) so users don't keep blank images.
                for p in video_path.parent.glob(f"{video_path.stem}-preview-*"):
                    try:
                        if p.is_file() and p.stat().st_size <= 4096:
                            p.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
        emit("artwork skip previews: no preview_urls")

    if opts.download_trailer and trailer_url:
        try:
            u = str(trailer_url)
            if ".m3u8" in u.lower():
                trailer_path = video_path.with_name(f"{video_path.stem}-trailer.mp4")
                ok = _download_hls(
                    u,
                    trailer_path,
                    proxy_url=opts.proxy_url,
                    headers=_headers_for(u),
                    log_fn=emit,
                )
            else:
                ext = _guess_file_ext(u, ".mp4")
                trailer_path = video_path.with_name(f"{video_path.stem}-trailer{ext}")
                # Avoid accidental huge downloads; cap at 200MB.
                ok = _download_file(
                    u,
                    trailer_path,
                    max_bytes=200 * 1024 * 1024,
                    proxy_url=opts.proxy_url,
                    headers=_headers_for(u),
                    log_fn=emit,
                )
            if emit and not ok:
                emit(f"warn: trailer not downloaded: {trailer_url}")
        except Exception:
            pass
    elif opts.download_trailer and emit:
        emit("trailer skip: no trailer_url")

    if "artwork" in include:
        if poster_name:
            _text_el(root, "poster", poster_name)
            _text_el(root, "cover", poster_name)
        if fanart_name:
            fanart_el = ET.SubElement(root, "fanart")
            _text_el(fanart_el, "thumb", fanart_name)

    if not opts.write_nfo:
        return None

    nfo_path = video_path.with_suffix(".nfo")
    try:
        ET.indent(root)  # py>=3.9
    except Exception:
        pass

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    nfo_path.write_bytes(xml)
    return nfo_path
