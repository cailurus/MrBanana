"""
Scrape worker — extracted from ScrapeManager._worker for readability.

Contains the actual scrape job execution logic: crawler instantiation,
directory scanning, metadata merging, and NFO/artwork writing.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import quote
from typing import TYPE_CHECKING

from mr_banana.utils.config import AppConfig, load_config
from mr_banana.utils.logger import logger

if TYPE_CHECKING:
    from api.scrape_manager import ScrapeManager


def run_scrape_worker(mgr: ScrapeManager, job_id: int) -> None:
    """Execute a scrape job. Called in a daemon thread by ScrapeManager.start_job."""
    with mgr._lock:
        job = mgr._jobs.get(job_id)
    if not job:
        return

    cfg = load_config()

    # Pre-scan eligible files so UI has total/current_file early.
    try:
        min_age_sec = 0.0 if job.ignore_min_age else mgr._get_scrape_min_age_sec(cfg)
        files = mgr._scan_eligible_videos(job.directory, min_age_sec=min_age_sec)
        first = str(files[0]) if files else None
        total = len(files)
        with mgr._lock:
            job.total = total
            job.current = int(job.current or 0)
            if (not job.current_file) and first:
                job.current_file = first
            job.status = "Running"
            mgr._persist_jobs_to_disk_locked()
    except Exception:
        with mgr._lock:
            job.status = "Running"
            mgr._persist_jobs_to_disk_locked()

    try:
        from mr_banana.scraper.crawlers.javbus import JavbusConfig, JavbusCrawler
        from mr_banana.scraper.crawlers.javdb import JavdbConfig, JavdbCrawler
        from mr_banana.scraper.crawlers.dmm import DmmConfig, DmmCrawler
        from mr_banana.scraper.crawlers.javtrailers import JavtrailersConfig, JavtrailersCrawler
        from mr_banana.scraper.crawlers.theporndb import ThePornDBConfig, ThePornDBCrawler
        from mr_banana.scraper.runner import scrape_directory
    except Exception as e:
        mgr._append_log(job_id, f"Scrape failed: init error: {e}")
        with mgr._lock:
            j = mgr._jobs.get(job_id)
            if j:
                j.status = "Failed"
                j.completed_at = time.time()
                mgr._persist_jobs_to_disk_locked()
        return

    use_proxy = bool(cfg.scrape_use_proxy)
    proxy_url = (cfg.scrape_proxy_url or "").strip() if use_proxy else ""

    def job_log(message: str) -> None:
        mgr._append_log(job_id, message)

    # Build per-field source map
    field_sources = _build_field_sources(cfg)

    sources_set: set[str] = set()
    for lst in field_sources.values():
        for s in lst or []:
            sources_set.add(str(s))

    if not sources_set:
        sources_set = set(cfg.scrape_sources or ["javbus", "dmm", "javdb"])

    # Create crawlers
    crawlers = _create_crawlers(
        sources_set, cfg, proxy_url, job_log,
        JavdbConfig=JavdbConfig, JavdbCrawler=JavdbCrawler,
        JavbusConfig=JavbusConfig, JavbusCrawler=JavbusCrawler,
        DmmConfig=DmmConfig, DmmCrawler=DmmCrawler,
        JavtrailersConfig=JavtrailersConfig, JavtrailersCrawler=JavtrailersCrawler,
        ThePornDBConfig=ThePornDBConfig, ThePornDBCrawler=ThePornDBCrawler,
    )

    if not crawlers:
        mgr._append_log(job_id, "Scrape failed: no sources enabled")
        with mgr._lock:
            job.status = "Failed"
            job.completed_at = time.time()
        return

    def progress_cb(current: int, total: int, current_file: str):
        with mgr._lock:
            j = mgr._jobs.get(job_id)
            if not j:
                return
            j.current = current
            j.total = total
            j.current_file = current_file

    try:
        out_dir_raw = (cfg.scrape_output_dir or "").strip()
        out_root = Path(out_dir_raw).expanduser().resolve() if out_dir_raw else None

        def to_item(r) -> dict:
            return _result_to_item(r, out_root)

        def item_cb(r) -> None:
            try:
                it = to_item(r)
                it["item_completed_at"] = time.time()
                with mgr._lock:
                    cur = list(mgr._items.get(job_id, []) or [])
                    cur.append(it)
                    mgr._items[job_id] = cur
                try:
                    mgr._persist_items_to_disk(job_id, cur)
                except Exception:
                    pass
            except Exception:
                return

        results = scrape_directory(
            job.directory,
            crawlers=crawlers,
            progress_cb=progress_cb,
            log_cb=job_log,
            item_cb=item_cb,
            options=_build_scrape_options(cfg, proxy_url, field_sources, job.ignore_min_age),
        )

        # Ensure final ordering is stable after completion.
        try:
            with mgr._lock:
                existing = list(mgr._items.get(job_id, []) or [])
            ts_by_path: dict[str, float] = {}
            for it in existing:
                try:
                    p = str((it or {}).get("path") or "").strip()
                    tsv = (it or {}).get("item_completed_at")
                    if p and isinstance(tsv, (int, float)):
                        ts_by_path[p] = float(tsv)
                except Exception:
                    continue

            final_items: list[dict] = []
            for r in (results or []):
                try:
                    it = to_item(r)
                    p = str(it.get("path") or "").strip()
                    if p and p in ts_by_path:
                        it["item_completed_at"] = ts_by_path[p]
                    final_items.append(it)
                except Exception:
                    continue
            with mgr._lock:
                mgr._items[job_id] = final_items
            mgr._persist_items_to_disk(job_id, final_items)
        except Exception as e:
            logger.debug(f"Failed to reconcile final items for job {job_id}: {e}")

        mgr._append_log(job_id, "Scrape finished")
        with mgr._lock:
            job.status = "Completed"
            job.completed_at = time.time()
            mgr._persist_jobs_to_disk_locked()
    except Exception as e:
        mgr._append_log(job_id, f"Scrape failed: {e}")
        with mgr._lock:
            job.status = "Failed"
            job.completed_at = time.time()
            mgr._persist_jobs_to_disk_locked()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_field_sources(cfg: AppConfig) -> dict[str, list[str]]:
    """Build per-field source mapping from config."""
    def _cfg_list(name: str) -> list[str]:
        v = getattr(cfg, name, None)
        return list(v or []) if isinstance(v, list) else []

    return {
        "title": _cfg_list("scrape_sources_title"),
        "plot": _cfg_list("scrape_sources_plot"),
        "actors": _cfg_list("scrape_sources_actors"),
        "tags": _cfg_list("scrape_sources_tags"),
        "release": _cfg_list("scrape_sources_release"),
        "runtime": _cfg_list("scrape_sources_runtime"),
        "studio": _cfg_list("scrape_sources_studio"),
        "publisher": _cfg_list("scrape_sources_publisher"),
        "trailer_url": _cfg_list("scrape_sources_trailer"),
        "rating": _cfg_list("scrape_sources_rating"),
        "poster_url": _cfg_list("scrape_sources_poster"),
        "fanart_url": _cfg_list("scrape_sources_fanart"),
        "preview_urls": _cfg_list("scrape_sources_previews"),
    }


def _create_crawlers(sources_set, cfg, proxy_url, job_log, **crawler_classes):
    """Instantiate crawlers for enabled sources in canonical order."""
    JavdbConfig = crawler_classes["JavdbConfig"]
    JavdbCrawler = crawler_classes["JavdbCrawler"]
    JavbusConfig = crawler_classes["JavbusConfig"]
    JavbusCrawler = crawler_classes["JavbusCrawler"]
    DmmConfig = crawler_classes["DmmConfig"]
    DmmCrawler = crawler_classes["DmmCrawler"]
    JavtrailersConfig = crawler_classes["JavtrailersConfig"]
    JavtrailersCrawler = crawler_classes["JavtrailersCrawler"]
    ThePornDBConfig = crawler_classes["ThePornDBConfig"]
    ThePornDBCrawler = crawler_classes["ThePornDBCrawler"]

    sources = [s for s in ["javbus", "dmm", "javdb", "javtrailers", "theporndb"] if s in sources_set]
    crawlers = []
    for s in sources:
        if s == "javdb":
            crawlers.append(JavdbCrawler(
                JavdbConfig(
                    cookie=cfg.javdb_cookie or "",
                    request_delay_sec=float(cfg.scrape_javdb_delay_sec or 0.0),
                    proxy_url=proxy_url,
                ), log_fn=job_log,
            ))
        elif s == "javbus":
            crawlers.append(JavbusCrawler(
                JavbusConfig(
                    cookie=cfg.javbus_cookie or "",
                    request_delay_sec=float(cfg.scrape_javbus_delay_sec or 0.0),
                    proxy_url=proxy_url,
                ), log_fn=job_log,
            ))
        elif s == "dmm":
            crawlers.append(DmmCrawler(
                DmmConfig(
                    request_delay_sec=float(cfg.scrape_javdb_delay_sec or 0.0),
                    proxy_url=proxy_url,
                ), log_fn=job_log,
            ))
        elif s == "javtrailers":
            crawlers.append(JavtrailersCrawler(
                JavtrailersConfig(
                    request_delay_sec=float(cfg.scrape_javdb_delay_sec or 0.0),
                    proxy_url=proxy_url,
                ), log_fn=job_log,
            ))
        elif s == "theporndb":
            crawlers.append(ThePornDBCrawler(
                ThePornDBConfig(
                    api_token=cfg.theporndb_api_token or "",
                    request_delay_sec=float(cfg.scrape_javdb_delay_sec or 0.0),
                    proxy_url=proxy_url,
                ), log_fn=job_log,
            ))
    return crawlers


def _build_scrape_options(cfg: AppConfig, proxy_url: str, field_sources: dict, ignore_min_age: bool) -> dict:
    """Build the options dict for scrape_directory()."""
    return {
        "output_dir": cfg.scrape_output_dir or "",
        "structure": cfg.scrape_structure or "{actor}/{year}/{code}",
        "rename": bool(cfg.scrape_rename),
        "copy_source": bool(cfg.scrape_copy_source),
        "existing_action": cfg.scrape_existing_action or "skip",
        "threads": int(cfg.scrape_threads or 1),
        "thread_delay_sec": float(cfg.scrape_thread_delay_sec or 0.0),
        "min_age_sec": 0.0 if ignore_min_age else float(cfg.scrape_trigger_watch_min_age_sec or 0.0),
        "write_nfo": bool(cfg.scrape_write_nfo),
        "download_poster": bool(cfg.scrape_download_poster),
        "download_fanart": bool(cfg.scrape_download_fanart),
        "download_previews": bool(cfg.scrape_download_previews),
        "download_trailer": bool(cfg.scrape_download_trailer),
        "download_subtitle": bool(cfg.scrape_download_subtitle),
        "subtitle_languages": list(cfg.scrape_subtitle_languages or []),
        "preview_limit": int(cfg.scrape_preview_limit or 8),
        "nfo_fields": list(cfg.scrape_nfo_fields or []),
        "translate_enabled": bool(cfg.scrape_translate_enabled),
        "translate_provider": cfg.scrape_translate_provider or "google",
        "translate_target_lang": cfg.scrape_translate_target_lang or "zh-CN",
        "translate_base_url": cfg.scrape_translate_base_url or "",
        "translate_api_key": cfg.scrape_translate_api_key or "",
        "translate_email": cfg.scrape_translate_email or "",
        "proxy_url": proxy_url,
        "field_sources": field_sources,
    }


def _result_to_item(r, out_root: Path | None) -> dict:
    """Convert a ScrapeItemResult to the dict format expected by the UI."""
    m = r.merged
    data = m.data or {}

    preview_local_urls: list[str] = []
    poster_local_url: str | None = None
    fanart_local_url: str | None = None
    trailer_local_url: str | None = None

    try:
        pdir = Path(str(r.path)).expanduser().resolve().parent
        video_stem = Path(str(r.path)).stem

        url_root = None
        if out_root and out_root.exists() and out_root.is_dir():
            try:
                pdir.relative_to(out_root)
                url_root = out_root
            except ValueError:
                url_root = pdir
        else:
            url_root = pdir

        if url_root and pdir.exists() and pdir.is_dir():
            # Local poster
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                poster_path = pdir / f"{video_stem}-poster{ext}"
                if poster_path.exists() and poster_path.is_file():
                    try:
                        rel = str(poster_path.relative_to(url_root))
                        poster_local_url = f"/api/library/file?rel={quote(rel)}"
                    except Exception:
                        pass
                    break

            # Local fanart
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                fanart_path = pdir / f"{video_stem}-fanart{ext}"
                if fanart_path.exists() and fanart_path.is_file():
                    try:
                        rel = str(fanart_path.relative_to(url_root))
                        fanart_local_url = f"/api/library/file?rel={quote(rel)}"
                    except Exception:
                        pass
                    break

            # Local previews
            preview_files = data.get("preview_files") or []
            if not preview_files:
                try:
                    preview_files = sorted(
                        [p.name for p in pdir.glob(f"{video_stem}-preview-*.*") if p.is_file()]
                    )
                except Exception:
                    preview_files = []

            for name in preview_files:
                try:
                    fp = (pdir / str(name)).resolve()
                    if not fp.exists() or not fp.is_file():
                        continue
                    rel = str(fp.relative_to(url_root))
                    preview_local_urls.append(f"/api/library/file?rel={quote(rel)}")
                except Exception:
                    continue
    except Exception:
        preview_local_urls = []

    # Local trailer
    try:
        trailer_file = data.get("trailer_file")
        if trailer_file and out_root:
            pdir = Path(str(r.path)).expanduser().resolve().parent
            trailer_fp = (pdir / str(trailer_file)).resolve()
            if trailer_fp.exists() and trailer_fp.is_file():
                rel = str(trailer_fp.relative_to(out_root))
                trailer_local_url = f"/api/library/file?rel={quote(rel)}"
    except Exception:
        pass

    return {
        "path": str(r.path),
        "title": m.title,
        "code": m.external_id,
        "url": m.original_url,
        "release": data.get("release"),
        "studio": data.get("studio"),
        "series": data.get("series"),
        "runtime": data.get("runtime"),
        "directors": data.get("directors") or [],
        "trailer_url": data.get("trailer_url"),
        "trailer_local_url": trailer_local_url,
        "plot": data.get("plot"),
        "actors": data.get("actors") or [],
        "tags": data.get("tags") or [],
        "poster_url": data.get("poster_url") or data.get("cover_url"),
        "poster_local_url": poster_local_url,
        "fanart_url": data.get("fanart_url") or data.get("cover_url"),
        "fanart_local_url": fanart_local_url,
        "preview_urls": data.get("preview_urls") or [],
        "preview_local_urls": preview_local_urls,
        "subtitles": [str(p) for p in (r.subtitles or [])],
    }
