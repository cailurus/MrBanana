from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class AppConfig:
    output_dir: str = ""
    max_concurrent_downloads: int = 5
    max_download_workers: int = 16
    filename_format: str = "{id}"

    # --- Downloader (optional) ---
    download_use_proxy: bool = False
    # Example: http://127.0.0.1:7890
    download_proxy_url: str = ""
    # best | 1080p | 720p | 480p | 360p
    download_resolution: str = "best"
    # Default choice in UI for "scrape after download"
    download_scrape_after_default: bool = False

    # --- Scraper (metadata & library organization) ---
    scrape_dir: str = ""

    # Scraper network
    scrape_use_proxy: bool = False
    # Example: http://127.0.0.1:7890
    scrape_proxy_url: str = ""

    # If empty, keep outputs next to the source video.
    scrape_output_dir: str = ""

    # --- Player (local library playback) ---
    # If set, the Player tab uses this as the media library root.
    # If empty, it falls back to scrape_output_dir.
    player_root_dir: str = ""
    # Directory template relative to output dir.
    # Placeholders: {actor} {year} {code} {title}
    scrape_structure: str = "{actor}/{year}/{code}"
    scrape_rename: bool = True

    # When output already exists: skip (default) | overwrite
    scrape_existing_action: str = "skip"

    # When output_dir is set, choose whether to copy (keep source) or move source video into library.
    # Default: keep source (copy).
    scrape_copy_source: bool = True

    # Concurrency & pacing
    scrape_threads: int = 1
    scrape_thread_delay_sec: float = 0.0
    scrape_javdb_delay_sec: float = 3.0
    scrape_javbus_delay_sec: float = 3.0

    # Upstream sources (order matters)
    scrape_sources: list[str] = field(default_factory=list)

    # Fallback upstream sources (order matters). Used when a field list is empty
    # and as the tail fallback when a field list is non-empty.
    scrape_sources_fallback: list[str] = field(default_factory=list)

    # Per-field upstream sources (order matters). If set, these override scrape_sources
    # for merging; the actual crawlers executed are the union of all enabled sources.
    scrape_sources_title: list[str] = field(default_factory=list)
    scrape_sources_plot: list[str] = field(default_factory=list)
    scrape_sources_actors: list[str] = field(default_factory=list)
    scrape_sources_tags: list[str] = field(default_factory=list)
    scrape_sources_release: list[str] = field(default_factory=list)
    scrape_sources_runtime: list[str] = field(default_factory=list)
    scrape_sources_directors: list[str] = field(default_factory=list)
    scrape_sources_series: list[str] = field(default_factory=list)
    scrape_sources_studio: list[str] = field(default_factory=list)
    scrape_sources_publisher: list[str] = field(default_factory=list)

    # Extra fields
    scrape_sources_trailer: list[str] = field(default_factory=list)
    scrape_sources_rating: list[str] = field(default_factory=list)
    scrape_sources_want: list[str] = field(default_factory=list)

    # Artwork fields
    scrape_sources_poster: list[str] = field(default_factory=list)
    scrape_sources_fanart: list[str] = field(default_factory=list)
    scrape_sources_previews: list[str] = field(default_factory=list)

    # ThePornDB (optional, requires API token)
    theporndb_api_token: str = ""

    # What to generate/download
    scrape_write_nfo: bool = True
    scrape_download_poster: bool = True
    scrape_download_fanart: bool = True
    scrape_download_previews: bool = True
    scrape_download_trailer: bool = True
    scrape_download_subtitle: bool = True
    scrape_subtitle_languages: list[str] = field(default_factory=list)
    scrape_preview_limit: int = 8

    # Which fields to include in NFO (subset of writer capabilities)
    scrape_nfo_fields: list[str] = field(default_factory=list)

    # --- Translation (optional) ---
    scrape_translate_enabled: bool = True
    # Providers: google | microsoft | deepl
    scrape_translate_provider: str = "google"
    # Source language: ja (Japanese) by default
    scrape_translate_source_lang: str = "ja"
    # Target language: en | zh-CN | zh-TW
    scrape_translate_target_lang: str = "zh-CN"
    # Advanced/compat fields:
    # - deepl uses scrape_translate_api_key as auth_key (required)
    # - scrape_translate_base_url can override DeepL host (optional)
    scrape_translate_base_url: str = ""
    scrape_translate_api_key: str = ""
    # (legacy field kept for backward compatibility)
    scrape_translate_email: str = ""

    # --- Triggering (optional automation) ---
    # manual | interval | watch
    scrape_trigger_mode: str = "manual"
    scrape_trigger_interval_sec: int = 3600
    scrape_trigger_watch_poll_sec: float = 10.0
    # Safety: only scrape files older than this (avoid interfering with ongoing downloads)
    scrape_trigger_watch_min_age_sec: float = 300.0
    # Require a quiet window (no eligible file changes) before triggering
    scrape_trigger_watch_quiet_sec: float = 30.0

    javdb_cookie: str = ""
    javbus_cookie: str = ""

    def __post_init__(self) -> None:
        # User requested deterministic upstream ordering + fallback semantics.
        fallback_default = ["javbus", "jav321", "dmm", "javdb"]

        if not self.scrape_sources:
            # Overall enabled sources for crawler execution (union is computed below).
            self.scrape_sources = list(fallback_default)

        if not self.scrape_sources_fallback:
            self.scrape_sources_fallback = list(fallback_default)

        if not self.scrape_subtitle_languages:
            self.scrape_subtitle_languages = ["zh", "ja"]

        # Implemented sources in this project.
        implemented = {"javdb", "jav321", "javbus", "dmm", "javtrailers", "theporndb"}

        # Per-field allowed sources (also used to limit UI options).
        allowed: dict[str, set[str]] = {
            "scrape_sources_fallback": {"javbus", "jav321", "dmm", "javdb"},
            "scrape_sources_title": {"dmm", "javtrailers"},
            "scrape_sources_plot": {"dmm"},
            "scrape_sources_actors": {"dmm", "javtrailers"},
            "scrape_sources_tags": {"dmm", "javtrailers"},
            "scrape_sources_release": {"dmm", "javtrailers"},
            "scrape_sources_runtime": {"dmm", "javtrailers"},
            "scrape_sources_directors": {"dmm"},
            "scrape_sources_series": {"dmm"},
            "scrape_sources_studio": {"dmm", "javtrailers"},
            "scrape_sources_publisher": {"dmm", "javtrailers"},
            "scrape_sources_trailer": {"javtrailers", "dmm"},
            "scrape_sources_rating": {"jav321", "javdb"},
            "scrape_sources_want": {"javdb"},
            "scrape_sources_poster": {"javtrailers", "javbus"},
            "scrape_sources_fanart": {"javtrailers", "javbus"},
            "scrape_sources_previews": {"javtrailers", "javbus"},
        }

        def _normalize_list(
            value: object,
            *,
            default: list[str],
            allow_empty: bool,
            allowed_sources: set[str] | None = None,
        ) -> list[str]:
            allowed_set = allowed_sources if allowed_sources is not None else implemented
            if not isinstance(value, list):
                value = list(default)
            elif not value and allow_empty:
                return []
            elif not value:
                value = list(default)
            out: list[str] = []
            seen: set[str] = set()
            for x in value:
                s = str(x).strip().lower()
                if not s or s in seen:
                    continue
                if s not in implemented:
                    continue
                if s not in allowed_set:
                    continue
                seen.add(s)
                out.append(s)
            if out:
                return out
            return [] if allow_empty else [s for s in default if s in implemented and s in allowed_set]

        enabled_union = _normalize_list(self.scrape_sources, default=fallback_default, allow_empty=False)
        self.scrape_sources_fallback = _normalize_list(
            self.scrape_sources_fallback,
            default=fallback_default,
            allow_empty=False,
            allowed_sources=allowed.get("scrape_sources_fallback"),
        )

        # Per-field defaults match the user-provided specification.
        self.scrape_sources_title = _normalize_list(
            self.scrape_sources_title,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_title"),
        )
        self.scrape_sources_plot = _normalize_list(
            self.scrape_sources_plot,
            default=["dmm"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_plot"),
        )
        self.scrape_sources_actors = _normalize_list(
            self.scrape_sources_actors,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_actors"),
        )
        self.scrape_sources_poster = _normalize_list(
            self.scrape_sources_poster,
            default=["javtrailers", "javbus"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_poster"),
        )
        self.scrape_sources_fanart = _normalize_list(
            self.scrape_sources_fanart,
            default=["javtrailers", "javbus"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_fanart"),
        )
        self.scrape_sources_previews = _normalize_list(
            self.scrape_sources_previews,
            default=["javtrailers", "javbus"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_previews"),
        )
        self.scrape_sources_trailer = _normalize_list(
            self.scrape_sources_trailer,
            default=["javtrailers", "dmm"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_trailer"),
        )

        self.scrape_sources_tags = _normalize_list(
            self.scrape_sources_tags,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_tags"),
        )
        self.scrape_sources_release = _normalize_list(
            self.scrape_sources_release,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_release"),
        )
        self.scrape_sources_runtime = _normalize_list(
            self.scrape_sources_runtime,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_runtime"),
        )
        self.scrape_sources_directors = _normalize_list(
            self.scrape_sources_directors,
            default=["dmm"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_directors"),
        )
        self.scrape_sources_series = _normalize_list(
            self.scrape_sources_series,
            default=["dmm"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_series"),
        )
        self.scrape_sources_studio = _normalize_list(
            self.scrape_sources_studio,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_studio"),
        )
        self.scrape_sources_publisher = _normalize_list(
            self.scrape_sources_publisher,
            default=["dmm", "javtrailers"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_publisher"),
        )

        self.scrape_sources_rating = _normalize_list(
            self.scrape_sources_rating,
            default=["jav321", "javdb"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_rating"),
        )
        self.scrape_sources_want = _normalize_list(
            self.scrape_sources_want,
            default=["javdb"],
            allow_empty=True,
            allowed_sources=allowed.get("scrape_sources_want"),
        )

        # Keep scrape_sources as the union for crawler execution.
        # Also enforce overall ordering: javbus -> jav321 -> dmm -> javdb -> javtrailers -> theporndb.
        union: list[str] = []
        for s in (self.scrape_sources_fallback or []):
            if s not in union:
                union.append(s)
        for lst in (
            self.scrape_sources_title,
            self.scrape_sources_plot,
            self.scrape_sources_actors,
            self.scrape_sources_tags,
            self.scrape_sources_release,
            self.scrape_sources_runtime,
            self.scrape_sources_directors,
            self.scrape_sources_series,
            self.scrape_sources_studio,
            self.scrape_sources_publisher,
            self.scrape_sources_trailer,
            self.scrape_sources_rating,
            self.scrape_sources_want,
            self.scrape_sources_poster,
            self.scrape_sources_fanart,
            self.scrape_sources_previews,
        ):
            for s in lst or []:
                if s not in union:
                    union.append(s)
        # Merge with any legacy enabled sources.
        for s in enabled_union:
            if s not in union:
                union.append(s)
        ordered = [s for s in ["javbus", "jav321", "dmm", "javdb", "javtrailers", "theporndb"] if s in union]
        self.scrape_sources = ordered
        if not self.scrape_nfo_fields:
            self.scrape_nfo_fields = [
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
            ]

        # Normalize trigger mode
        if self.scrape_trigger_mode not in {"manual", "interval", "watch"}:
            self.scrape_trigger_mode = "manual"

        # Normalize translation provider/lang
        if self.scrape_translate_provider not in {"google", "microsoft", "deepl"}:
            self.scrape_translate_provider = "google"
        if self.scrape_translate_target_lang not in {"en", "zh-CN", "zh-TW"}:
            self.scrape_translate_target_lang = "zh-CN"

        # Normalize downloader settings
        if self.download_resolution not in {"best", "1080p", "720p", "480p", "360p"}:
            self.download_resolution = "best"

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {k: v for k, v in self.__dict__.items()}


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return AppConfig()

    cfg = AppConfig()
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    # Re-normalize after applying persisted values.
    try:
        cfg.__post_init__()
    except Exception:
        pass
    return cfg


def save_config(cfg: AppConfig) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg.__dict__, ensure_ascii=False, indent=4), encoding="utf-8")
