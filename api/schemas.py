from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field, field_validator


# Constants for validation
MAX_URL_LENGTH = 2048
MAX_PATH_LENGTH = 1024
MAX_PROXY_URL_LENGTH = 512


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=MAX_URL_LENGTH)
    output_dir: str = Field(default="", max_length=MAX_PATH_LENGTH)
    scrape_after_download: bool = False

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('URL cannot be empty')
        # Basic URL validation - must be http/https or a code pattern
        if v.startswith(('http://', 'https://')):
            return v
        # Allow code patterns like "ABC-123"
        if len(v) <= 50:
            return v
        raise ValueError('Invalid URL format')


class DownloadConfigRequest(BaseModel):
    output_dir: str | None = Field(default=None, max_length=MAX_PATH_LENGTH)
    max_download_workers: int | None = Field(default=None, ge=1, le=128)
    filename_format: str | None = Field(default=None, max_length=256)
    download_use_proxy: bool | None = None
    download_proxy_url: str | None = Field(default=None, max_length=MAX_PROXY_URL_LENGTH)
    download_resolution: str | None = None
    download_scrape_after_default: bool | None = None


class ResumeRequest(BaseModel):
    task_id: int = Field(..., ge=1)
    output_dir: str = Field(default="", max_length=MAX_PATH_LENGTH)


class TaskRequest(BaseModel):
    task_id: int = Field(..., ge=1)


class ScrapeConfigRequest(BaseModel):
    scrape_dir: str | None = None
    scrape_use_proxy: bool | None = None
    scrape_proxy_url: str | None = None
    scrape_output_dir: str | None = None
    scrape_structure: str | None = None
    scrape_rename: bool | None = None
    scrape_copy_source: bool | None = None
    scrape_existing_action: str | None = None
    scrape_threads: int | None = None
    scrape_thread_delay_sec: float | None = None
    scrape_javdb_delay_sec: float | None = None
    scrape_javbus_delay_sec: float | None = None
    scrape_sources: List[str] | None = None

    # Fallback sources (used when a field list is empty)
    scrape_sources_fallback: List[str] | None = None

    # Per-field sources (order matters). If provided, each field can use different upstreams.
    scrape_sources_title: List[str] | None = None
    scrape_sources_plot: List[str] | None = None
    scrape_sources_actors: List[str] | None = None
    scrape_sources_tags: List[str] | None = None
    scrape_sources_release: List[str] | None = None
    scrape_sources_runtime: List[str] | None = None
    scrape_sources_directors: List[str] | None = None
    scrape_sources_series: List[str] | None = None
    scrape_sources_studio: List[str] | None = None
    scrape_sources_publisher: List[str] | None = None
    scrape_sources_trailer: List[str] | None = None
    scrape_sources_rating: List[str] | None = None
    scrape_sources_want: List[str] | None = None
    scrape_sources_poster: List[str] | None = None
    scrape_sources_fanart: List[str] | None = None
    scrape_sources_previews: List[str] | None = None
    scrape_write_nfo: bool | None = None
    scrape_download_poster: bool | None = None
    scrape_download_fanart: bool | None = None
    scrape_download_previews: bool | None = None
    scrape_download_trailer: bool | None = None
    scrape_download_subtitle: bool | None = None
    scrape_subtitle_languages: List[str] | None = None
    scrape_preview_limit: int | None = None
    scrape_nfo_fields: List[str] | None = None

    # Translation
    scrape_translate_enabled: bool | None = None
    scrape_translate_provider: str | None = None
    scrape_translate_target_lang: str | None = None
    scrape_translate_base_url: str | None = None
    scrape_translate_api_key: str | None = None
    scrape_translate_email: str | None = None

    # Trigger
    scrape_trigger_mode: str | None = None
    scrape_trigger_interval_sec: int | None = None
    scrape_trigger_watch_poll_sec: float | None = None
    scrape_trigger_watch_min_age_sec: float | None = None
    scrape_trigger_watch_quiet_sec: float | None = None

    # ThePornDB (optional)
    theporndb_api_token: str | None = None


class ScrapeStartRequest(BaseModel):
    directory: str


class ChooseDirectoryRequest(BaseModel):
    title: str | None = None
    initial_dir: str | None = None


class OpenPathRequest(BaseModel):
    path: str
    reveal: bool | None = True


class PlayerConfigRequest(BaseModel):
    player_root_dir: str | None = None
