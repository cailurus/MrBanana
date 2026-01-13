from __future__ import annotations

import re

from .types import CrawlResult


_DEFAULT_FIELD_SOURCE_PRIORITY: dict[str, list[str]] = {
    "title": ["javtrailers"],
    "plot": ["dmm"],
    "actors": ["javtrailers"],
    "poster_url": ["javtrailers"],
    "fanart_url": ["javtrailers"],
    "preview_urls": ["javtrailers"],
    "trailer_url": ["javtrailers"],
    "tags": ["javtrailers"],
    "release": ["javtrailers"],
    "runtime": ["javtrailers"],
    "directors": ["javtrailers"],
    "series": ["javtrailers"],
    "studio": ["javtrailers"],
}


def _field_disabled(field: str, field_sources: dict[str, list[str]] | None) -> bool:
    if not field_sources or field not in field_sources:
        return False
    v = field_sources.get(field)
    return isinstance(v, list) and len(v) == 0


def _rank_for(field: str, source: str, field_sources: dict[str, list[str]] | None = None) -> int:
    selected: list[str] = []
    if field_sources and isinstance(field_sources.get(field), list):
        selected = list(field_sources.get(field) or [])

    # Semantics (no fallback):
    # - If user selected providers for a field, try them in order.
    # - If user selected none (empty list), the field is considered disabled.
    # - If field is not present in field_sources, fall back to default priority.
    pref: list[str] | None
    if field_sources and field in field_sources:
        pref = list(selected)
    else:
        pref = _DEFAULT_FIELD_SOURCE_PRIORITY.get(field)

    if not pref:
        return 10_000
    try:
        return pref.index(source)
    except ValueError:
        return 10_000


def _is_probably_code(s: str) -> bool:
    t = (s or "").strip()
    return bool(re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9]+", t))


def _looks_meta_plot(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    if any(m in t for m in ("番号搜磁链", "管理你的成人影片", "分享你的想法")):
        return True
    # Chinese variants
    if "发布日期" in t and ("时长" in t or "長度" in t) and ("分钟" in t or "分鐘" in t):
        return True
    # Traditional/JavBus variants
    if "發行日期" in t and "長度" in t and "分鐘" in t:
        return True
    if re.search(r"(?:\[|［)\s*发布日期\s*(?:\]|］)", t):
        return True
    if re.search(r"(?:\[|［)\s*时长\s*(?:\]|］)", t):
        return True
    if re.search(r"【\s*(?:發行日期|发行日期|发布日期)\s*】", t):
        return True
    if re.search(r"【\s*(?:長度|长度|时长)\s*】", t):
        return True
    return False


def _looks_placeholder_plot(s: str) -> bool:
    """Detect non-plot placeholders from blocked/JS-only pages."""
    t = re.sub(r"\s+", " ", (s or "").strip()).lower()
    if not t:
        return True
    bad_markers = [
        # Japanese DMM placeholders
        "javascriptを有効",
        "java scriptを有効",
        "javascriptの設定方法",
        "無料サンプル",
        "サンプル動画",
        "中古品",
        "画像をクリックして拡大",
        "拡大サンプル画像",
        "安心な梱包",
        # Chinese placeholders
        "请启用javascript",
        "如何设置javascript",
        "单击图像放大",
        "图像仅供说明",
        "安全包装",
    ]
    if any(m in t for m in bad_markers):
        return True
    # If it's extremely short, treat as invalid plot.
    return len(t) < 20


def _looks_bad_plot(s: str) -> bool:
    return _looks_placeholder_plot(s) or _looks_meta_plot(s)


def _valid_url(s: object) -> str | None:
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    if t.startswith("http://") or t.startswith("https://"):
        return t
    return None


def _derive_dmm_artwork(cover_url: str | None) -> tuple[str | None, str | None]:
    """Derive DMM poster/fanart variants from a cover url.

    DMM commonly uses:
    - ...ps.jpg (poster, portrait)
    - ...pl.jpg (fanart, landscape)
    """
    u = str(cover_url or "").strip()
    if not u:
        return None, None
    low = u.lower()
    if "pics.dmm.co.jp/" not in low:
        return None, None
    if re.search(r"(?i)ps\.jpg(?=$|\?)", u):
        poster = u
        fanart = re.sub(r"(?i)ps\.jpg(?=$|\?)", "pl.jpg", u, count=1)
        return poster, fanart
    if re.search(r"(?i)pl\.jpg(?=$|\?)", u):
        fanart = u
        poster = re.sub(r"(?i)pl\.jpg(?=$|\?)", "ps.jpg", u, count=1)
        return poster, fanart
    return None, None


def _pick_by_priority(results: list[CrawlResult], field: str, getter, field_sources: dict[str, list[str]] | None = None) -> object | None:
    if _field_disabled(field, field_sources):
        return None
    indexed = list(enumerate(results))
    indexed.sort(key=lambda it: (_rank_for(field, getattr(it[1], "source", ""), field_sources), it[0]))
    for _, r in indexed:
        try:
            v = getter(r)
        except Exception:
            v = None
        if v in (None, "") or v == [] or v == {}:
            continue
        return v
    return None

def merge_results(results: list[CrawlResult], *, field_sources: dict[str, list[str]] | None = None) -> CrawlResult:
    """Merge multiple crawler results.

    Strategy:
    - Per-field upstream priority (A->B fallback) for key fields like title/plot/actors/artwork.
    - Fallback to first-non-empty (crawler order) for any remaining fields.
    """
    merged = CrawlResult(source="merged")

    # External id + canonical url (keep simple and stable)
    for r in results:
        if not merged.external_id and r.external_id:
            merged.external_id = r.external_id
        if not merged.original_url and r.original_url:
            merged.original_url = r.original_url

    # Title (avoid pure-code titles; avoid extremely long marketing titles when better options exist)
    picked_title = _pick_by_priority(
        results,
        "title",
        lambda r: (r.title.strip() if isinstance(r.title, str) else None),
        field_sources,
    )
    if not _field_disabled("title", field_sources):
        if isinstance(picked_title, str) and picked_title.strip() and not _is_probably_code(picked_title):
            merged.title = picked_title.strip()
        else:
            # fallback: first non-empty title
            for r in results:
                if r.title:
                    merged.title = r.title
                    break

    # Per-field data selection
    plot_val = _pick_by_priority(results, "plot", lambda r: (r.data or {}).get("plot"), field_sources)
    if not _field_disabled("plot", field_sources):
        if isinstance(plot_val, str) and plot_val.strip() and not _looks_bad_plot(plot_val):
            merged.data["plot"] = plot_val.strip()
        else:
            # If best-by-priority looks like meta/placeholder, try any other non-bad plot
            for r in results:
                v = (r.data or {}).get("plot")
                if isinstance(v, str) and v.strip() and not _looks_bad_plot(v):
                    merged.data["plot"] = v.strip()
                    break
            else:
                if isinstance(plot_val, str) and plot_val.strip():
                    # Keep the last-resort plot (even if bad) so user can see what happened.
                    merged.data["plot"] = plot_val.strip()

    for key in (
        "actors",
        "studio",
        "series",
        "release",
        "runtime",
        "directors",
        "tags",
    ):
        if _field_disabled(key, field_sources):
            continue
        v = _pick_by_priority(results, key, lambda r, k=key: (r.data or {}).get(k), field_sources)
        if v not in (None, "") and v != [] and v != {}:
            merged.data[key] = v

    trailer = _pick_by_priority(
        results,
        "trailer_url",
        lambda r: _valid_url((r.data or {}).get("trailer_url")),
        field_sources,
    )
    if not _field_disabled("trailer_url", field_sources):
        if isinstance(trailer, str):
            merged.data["trailer_url"] = trailer

    # Artwork fields
    poster = _pick_by_priority(
        results,
        "poster_url",
        lambda r: (
            _valid_url((r.data or {}).get("poster_url"))
            or _derive_dmm_artwork(_valid_url((r.data or {}).get("cover_url")))[0]
            or _valid_url((r.data or {}).get("cover_url"))
        ),
        field_sources,
    )
    fanart = _pick_by_priority(
        results,
        "fanart_url",
        lambda r: (
            _valid_url((r.data or {}).get("fanart_url"))
            or _derive_dmm_artwork(_valid_url((r.data or {}).get("cover_url")))[1]
        ),
        field_sources,
    )
    previews = _pick_by_priority(results, "preview_urls", lambda r: (r.data or {}).get("preview_urls"), field_sources)

    if not _field_disabled("poster_url", field_sources):
        if isinstance(poster, str):
            merged.data["poster_url"] = poster

    if not _field_disabled("fanart_url", field_sources):
        if isinstance(fanart, str):
            merged.data["fanart_url"] = fanart

    if not _field_disabled("preview_urls", field_sources):
        if isinstance(previews, list) and previews:
            merged.data["preview_urls"] = previews

    # Fallback: fill remaining keys by first non-empty in crawler order.
    for r in results:
        for k, v in (r.data or {}).items():
            if k in merged.data:
                continue
            if v in (None, "") or v == [] or v == {}:
                continue
            merged.data[k] = v

    return merged
