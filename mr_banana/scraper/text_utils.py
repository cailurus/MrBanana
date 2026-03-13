"""Shared text validation and artwork utilities for scrapers.

Centralises plot-quality checks and DMM artwork derivation that were
previously duplicated across merger.py, dmm.py, javbus.py, javdb.py,
and javtrailers.py.
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Plot / description quality checks
# ---------------------------------------------------------------------------

def looks_placeholder_plot(s: str) -> bool:
    """Detect non-plot placeholders from blocked / JS-only pages."""
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
    # Extremely short text is almost never a real plot.
    return len(t) < 20


def looks_meta_plot(s: str) -> bool:
    """Detect metadata-style text that is *not* a real plot synopsis."""
    t = (s or "").strip()
    if not t:
        return False
    if any(m in t for m in ("番号搜磁链", "管理你的成人影片", "分享你的想法")):
        return True
    # Chinese variants
    if "发布日期" in t and ("时长" in t or "長度" in t) and ("分钟" in t or "分鐘" in t):
        return True
    # Traditional Chinese variants
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


def looks_bad_plot(s: str) -> bool:
    """Return True if *s* looks like placeholder text or metadata, not a real plot."""
    return looks_placeholder_plot(s) or looks_meta_plot(s)


def looks_generic_site_desc(s: str) -> bool:
    """Detect generic site tagline / SEO descriptions that aren't real plots.

    Shared by JavDB and JavBus meta-description checks.
    """
    t = (s or "").strip()
    if not t:
        return True
    bad_markers = [
        "番号搜磁链",
        "管理你的成人影片",
        "分享你的想法",
    ]
    if any(m in t for m in bad_markers):
        return True
    if len(t) < 30:
        return True
    return False


# ---------------------------------------------------------------------------
# Code & date normalisation helpers
# ---------------------------------------------------------------------------

def normalize_code(s: str) -> str:
    """Strip non-alphanumeric chars and uppercase, for code comparison."""
    return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())


def normalize_release_date(s: str) -> str:
    """Normalize date strings to YYYY-MM-DD format.

    Handles:
    - ISO 8601: ``2025-11-21T03:00:00.000Z`` -> ``2025-11-21``
    - Partial dates with slashes or short fields: ``2025/1/5`` -> ``2025-01-05``

    Returns the original string unchanged when no pattern matches.
    """
    t = (s or "").strip()
    if not t:
        return t
    # ISO 8601 with a 'T' separator – just take the date part.
    if "T" in t:
        t = t.split("T")[0]
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", t)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        return f"{y}-{mo}-{d}"
    return t


# ---------------------------------------------------------------------------
# DMM artwork URL derivation
# ---------------------------------------------------------------------------

def derive_dmm_artwork(cover_url: str | None) -> tuple[str | None, str | None]:
    """Derive DMM poster/fanart variants from a cover URL.

    DMM commonly uses:
    - ...ps.jpg  (poster, portrait)
    - ...pl.jpg  (fanart, landscape)

    Returns (poster_url, fanart_url).
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
