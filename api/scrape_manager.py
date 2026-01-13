from __future__ import annotations

import os
import re
import threading
import time
import json
from pathlib import Path
from urllib.parse import quote
from dataclasses import dataclass

from mr_banana.utils.config import AppConfig, load_config, save_config
from mr_banana.utils.logger import logger, LOGS_DIR


@dataclass
class ScrapeJob:
    id: int
    directory: str
    status: str
    created_at: float
    completed_at: float | None = None
    current: int = 0
    total: int = 0
    current_file: str | None = None
    ignore_min_age: bool = False


class ScrapeManager:
    def __init__(self):
        self._jobs: dict[int, ScrapeJob] = {}
        self._items: dict[int, list[dict]] = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._logs_dir = os.path.join(LOGS_DIR, "task_logs")
        os.makedirs(self._logs_dir, exist_ok=True)
        self._jobs_path = os.path.join(self._logs_dir, "scrape_jobs.json")

        # Per-job item snapshots (written on completion; used to build per-movie history)
        self._items_dir = os.path.join(self._logs_dir, "scrape_items")
        os.makedirs(self._items_dir, exist_ok=True)

        # Best-effort restore of previous scrape job history.
        self._load_jobs_from_disk()

        # Auto-trigger state
        self._auto_last_trigger_at: float = 0.0
        self._auto_last_fingerprint: str | None = None
        self._auto_last_change_at: float = 0.0
        self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self._auto_thread.start()

    def _get_scrape_min_age_sec(self, cfg: AppConfig | None = None) -> float:
        try:
            c = cfg or load_config()
            return float(getattr(c, "scrape_trigger_watch_min_age_sec", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _scan_eligible_videos(self, root_dir: str, *, min_age_sec: float) -> list[Path]:
        """Scan videos with the same logic as the runner, with optional min-age filtering."""
        try:
            from mr_banana.scraper.file_scanner import scan_videos

            files = scan_videos(root_dir)
            if not (min_age_sec and min_age_sec > 0):
                return files

            now = time.time()
            eligible: list[Path] = []
            for p in files:
                try:
                    st = p.stat()
                    if now - float(st.st_mtime) >= float(min_age_sec):
                        eligible.append(p)
                except Exception:
                    continue
            return eligible
        except Exception:
            return []

    def _peek_first_video(self, root_dir: str, *, min_age_sec: float) -> str | None:
        """Best-effort find the first eligible video path for early UI display."""
        try:
            files = self._scan_eligible_videos(root_dir, min_age_sec=min_age_sec)
            return str(files[0]) if files else None
        except Exception:
            return None

    def pending_count(self, directory: str | None = None, *, ignore_min_age: bool = False) -> dict:
        """Count pending (eligible) videos in a directory.

        If directory is omitted, uses the configured scrape_dir.
        """
        try:
            cfg = load_config()
            root_dir = str(directory or getattr(cfg, "scrape_dir", "") or "").strip()
            if not root_dir:
                return {"status": "error", "message": "scrape_dir is empty", "directory": root_dir, "count": 0}
            if not os.path.isdir(root_dir):
                return {"status": "error", "message": "scrape_dir is not a directory", "directory": root_dir, "count": 0}

            min_age_sec = 0.0 if ignore_min_age else self._get_scrape_min_age_sec(cfg)
            files = self._scan_eligible_videos(root_dir, min_age_sec=min_age_sec)
            return {
                "status": "success",
                "directory": root_dir,
                "count": int(len(files)),
                "min_age_sec": float(min_age_sec),
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "directory": str(directory or ""), "count": 0}

    def _load_jobs_from_disk(self) -> None:
        try:
            if not os.path.exists(self._jobs_path):
                return
            raw = Path(self._jobs_path).read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return
            jobs_list = data.get("jobs")
            next_id = data.get("next_id")
            if not isinstance(jobs_list, list):
                return

            restored: dict[int, ScrapeJob] = {}
            max_seen = 0
            for it in jobs_list:
                if not isinstance(it, dict):
                    continue
                try:
                    jid = int(it.get("id") or 0)
                except Exception:
                    continue
                if jid <= 0:
                    continue
                max_seen = max(max_seen, jid)
                restored[jid] = ScrapeJob(
                    id=jid,
                    directory=str(it.get("directory") or ""),
                    status=str(it.get("status") or "Pending"),
                    created_at=float(it.get("created_at") or 0.0),
                    completed_at=(float(it["completed_at"]) if it.get("completed_at") is not None else None),
                    current=int(it.get("current") or 0),
                    total=int(it.get("total") or 0),
                    current_file=(str(it.get("current_file")) if it.get("current_file") else None),
                    ignore_min_age=bool(it.get("ignore_min_age") or False),
                )

            with self._lock:
                self._jobs = restored
                if isinstance(next_id, (int, float)) and int(next_id) > 0:
                    self._next_id = int(next_id)
                else:
                    self._next_id = max_seen + 1
        except Exception:
            return

    def _persist_jobs_to_disk_locked(self) -> None:
        # Caller must hold self._lock.
        try:
            jobs = sorted(self._jobs.values(), key=lambda j: j.id, reverse=True)[:200]
            payload = {
                "next_id": int(self._next_id),
                "jobs": [j.__dict__ for j in jobs],
            }
            tmp = self._jobs_path + ".tmp"
            Path(tmp).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self._jobs_path)
        except Exception:
            return

    def _has_running_job(self) -> bool:
        with self._lock:
            return any(j.status == "Running" for j in self._jobs.values())

    def _fingerprint_directory(self, root_dir: str, *, min_age_sec: float) -> str:
        """Create a lightweight fingerprint of eligible video files in a directory."""
        try:
            from mr_banana.scraper.file_scanner import scan_videos

            now = time.time()
            parts: list[str] = []
            for p in scan_videos(root_dir):
                try:
                    st = p.stat()
                    if min_age_sec and (now - float(st.st_mtime) < float(min_age_sec)):
                        continue
                    parts.append(f"{p.name}:{st.st_size}:{int(st.st_mtime)}")
                except Exception:
                    continue
            parts.sort()
            return "|".join(parts)
        except Exception:
            return ""

    def _auto_loop(self) -> None:
        """Background loop to auto-start scrape jobs based on config."""
        while True:
            try:
                cfg = load_config()
                mode = str(getattr(cfg, "scrape_trigger_mode", "manual") or "manual")
                if mode not in {"manual", "interval", "watch"}:
                    mode = "manual"

                # Never auto-start if a job is running.
                if self._has_running_job():
                    time.sleep(1.0)
                    continue

                scrape_dir = str(getattr(cfg, "scrape_dir", "") or "").strip()
                if not scrape_dir or not os.path.isdir(scrape_dir):
                    time.sleep(2.0)
                    continue

                now = time.time()

                if mode == "interval":
                    interval_sec = int(getattr(cfg, "scrape_trigger_interval_sec", 3600) or 3600)
                    interval_sec = max(30, interval_sec)
                    if now - float(self._auto_last_trigger_at or 0.0) >= float(interval_sec):
                        res = self.start_job(scrape_dir)
                        if res.get("status") == "success":
                            self._auto_last_trigger_at = now
                    time.sleep(1.0)
                    continue

                if mode == "watch":
                    poll_sec = float(getattr(cfg, "scrape_trigger_watch_poll_sec", 10.0) or 10.0)
                    poll_sec = max(2.0, min(poll_sec, 120.0))
                    min_age_sec = float(getattr(cfg, "scrape_trigger_watch_min_age_sec", 300.0) or 300.0)
                    quiet_sec = float(getattr(cfg, "scrape_trigger_watch_quiet_sec", 30.0) or 30.0)
                    quiet_sec = max(5.0, min(quiet_sec, 600.0))

                    fp = self._fingerprint_directory(scrape_dir, min_age_sec=min_age_sec)
                    if self._auto_last_fingerprint is None:
                        self._auto_last_fingerprint = fp
                        self._auto_last_change_at = now
                        time.sleep(poll_sec)
                        continue

                    if fp != self._auto_last_fingerprint:
                        self._auto_last_fingerprint = fp
                        self._auto_last_change_at = now
                        time.sleep(poll_sec)
                        continue

                    if fp and (now - float(self._auto_last_change_at or 0.0) >= quiet_sec):
                        # Debounce triggers
                        if now - float(self._auto_last_trigger_at or 0.0) >= max(quiet_sec, 30.0):
                            res = self.start_job(scrape_dir)
                            if res.get("status") == "success":
                                self._auto_last_trigger_at = now
                                # force a new change window before next trigger
                                self._auto_last_change_at = now
                    time.sleep(poll_sec)
                    continue

                # manual
                time.sleep(2.0)
            except Exception:
                time.sleep(2.0)

    def get_config(self) -> dict:
        cfg = load_config()
        return {
            "scrape_dir": cfg.scrape_dir,
            "scrape_use_proxy": bool(getattr(cfg, "scrape_use_proxy", False)),
            "scrape_proxy_url": str(getattr(cfg, "scrape_proxy_url", "") or ""),
            "scrape_output_dir": getattr(cfg, "scrape_output_dir", "") or "",
            "scrape_structure": getattr(cfg, "scrape_structure", "{actor}/{year}/{code}") or "{actor}/{year}/{code}",
            "scrape_rename": bool(getattr(cfg, "scrape_rename", True)),
            "scrape_copy_source": bool(getattr(cfg, "scrape_copy_source", True)),
            "scrape_existing_action": str(getattr(cfg, "scrape_existing_action", "skip") or "skip"),
            "scrape_threads": int(getattr(cfg, "scrape_threads", 1) or 1),
            "scrape_thread_delay_sec": float(getattr(cfg, "scrape_thread_delay_sec", 0.0) or 0.0),
            "scrape_javdb_delay_sec": float(getattr(cfg, "scrape_javdb_delay_sec", 0.0) or 0.0),
            "scrape_javbus_delay_sec": float(getattr(cfg, "scrape_javbus_delay_sec", 0.0) or 0.0),
            "scrape_sources": list(getattr(cfg, "scrape_sources", ["javdb", "javbus"]) or ["javdb", "javbus"]),

            # Fallback sources
            "scrape_sources_fallback": list(getattr(cfg, "scrape_sources_fallback", ["javbus", "dmm", "javdb"]) or ["javbus", "dmm", "javdb"]),

            # Per-field sources
            "scrape_sources_title": list(getattr(cfg, "scrape_sources_title", []) or []),
            "scrape_sources_plot": list(getattr(cfg, "scrape_sources_plot", []) or []),
            "scrape_sources_actors": list(getattr(cfg, "scrape_sources_actors", []) or []),
            "scrape_sources_tags": list(getattr(cfg, "scrape_sources_tags", []) or []),
            "scrape_sources_release": list(getattr(cfg, "scrape_sources_release", []) or []),
            "scrape_sources_runtime": list(getattr(cfg, "scrape_sources_runtime", []) or []),
            "scrape_sources_directors": list(getattr(cfg, "scrape_sources_directors", []) or []),
            "scrape_sources_series": list(getattr(cfg, "scrape_sources_series", []) or []),
            "scrape_sources_studio": list(getattr(cfg, "scrape_sources_studio", []) or []),
            "scrape_sources_publisher": list(getattr(cfg, "scrape_sources_publisher", []) or []),
            "scrape_sources_trailer": list(getattr(cfg, "scrape_sources_trailer", []) or []),
            "scrape_sources_rating": list(getattr(cfg, "scrape_sources_rating", []) or []),
            "scrape_sources_poster": list(getattr(cfg, "scrape_sources_poster", []) or []),
            "scrape_sources_fanart": list(getattr(cfg, "scrape_sources_fanart", []) or []),
            "scrape_sources_previews": list(getattr(cfg, "scrape_sources_previews", []) or []),
            "scrape_write_nfo": bool(getattr(cfg, "scrape_write_nfo", True)),
            "scrape_download_poster": bool(getattr(cfg, "scrape_download_poster", True)),
            "scrape_download_fanart": bool(getattr(cfg, "scrape_download_fanart", True)),
            "scrape_download_previews": bool(getattr(cfg, "scrape_download_previews", False)),
            "scrape_download_trailer": bool(getattr(cfg, "scrape_download_trailer", False)),
            "scrape_download_subtitle": bool(getattr(cfg, "scrape_download_subtitle", False)),
            "scrape_subtitle_languages": list(getattr(cfg, "scrape_subtitle_languages", []) or []),
            "scrape_preview_limit": int(getattr(cfg, "scrape_preview_limit", 8) or 8),
            "scrape_nfo_fields": list(getattr(cfg, "scrape_nfo_fields", []) or []),

            # Translation
            "scrape_translate_enabled": bool(getattr(cfg, "scrape_translate_enabled", False)),
            "scrape_translate_provider": str(getattr(cfg, "scrape_translate_provider", "google") or "google"),
            "scrape_translate_target_lang": str(getattr(cfg, "scrape_translate_target_lang", "zh-CN") or "zh-CN"),
            "scrape_translate_base_url": str(getattr(cfg, "scrape_translate_base_url", "") or ""),
            "scrape_translate_api_key": str(getattr(cfg, "scrape_translate_api_key", "") or ""),
            "scrape_translate_email": str(getattr(cfg, "scrape_translate_email", "") or ""),

            # Trigger
            "scrape_trigger_mode": str(getattr(cfg, "scrape_trigger_mode", "manual") or "manual"),
            "scrape_trigger_interval_sec": int(getattr(cfg, "scrape_trigger_interval_sec", 3600) or 3600),
            "scrape_trigger_watch_poll_sec": float(getattr(cfg, "scrape_trigger_watch_poll_sec", 10.0) or 10.0),
            "scrape_trigger_watch_min_age_sec": float(getattr(cfg, "scrape_trigger_watch_min_age_sec", 300.0) or 300.0),
            "scrape_trigger_watch_quiet_sec": float(getattr(cfg, "scrape_trigger_watch_quiet_sec", 30.0) or 30.0),

            # ThePornDB (optional)
            "theporndb_api_token": str(getattr(cfg, "theporndb_api_token", "") or ""),
        }

    def set_config(self, **updates) -> dict:
        cfg = load_config()

        # Only set known attributes to keep config stable.
        for k, v in (updates or {}).items():
            if v is None:
                continue
            if hasattr(cfg, k):
                setattr(cfg, k, v)

        save_config(cfg)
        return self.get_config()

    def list_jobs(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.id, reverse=True)[:limit]
        return [job.__dict__ for job in jobs]

    def list_items(self, job_id: int, limit: int = 500) -> list[dict]:
        jid = int(job_id)
        with self._lock:
            items = list(self._items.get(jid, []) or [])
        if not items:
            # Best-effort restore from disk (useful after backend restart)
            loaded = self._load_items_from_disk(jid)
            if loaded:
                with self._lock:
                    self._items[jid] = list(loaded)
                items = list(loaded)
        return items[: max(1, int(limit or 500))]

    def list_history_items(self, limit_jobs: int = 20, limit_items_per_job: int = 500) -> list[dict]:
        """Flatten job->items into per-movie history rows for UI."""
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.id, reverse=True)[: max(1, int(limit_jobs or 20))]

        rows: list[dict] = []
        for j in jobs:
            cur_path = str(j.current_file or "").strip() if j.status in {"Running", "Starting"} else ""
            items = self.list_items(j.id, limit=limit_items_per_job)
            item_rows: list[dict] = []
            if items:
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    item_rows.append(
                        {
                            **it,
                            "job_id": j.id,
                            "job_status": j.status,
                            "job_created_at": j.created_at,
                            "job_completed_at": j.completed_at,
                            "job_current": j.current,
                            "job_total": j.total,
                            "job_current_file": j.current_file,
                        }
                    )

            # If job is running, always include a synthetic "current" row so UI can show progress
            # even before the current movie is completed.
            if cur_path:
                already = False
                for rr in item_rows:
                    try:
                        if str(rr.get("path") or "").strip() == cur_path:
                            already = True
                            break
                    except Exception:
                        continue
                if not already:
                    rows.append(
                        {
                            "job_id": j.id,
                            "job_status": j.status,
                            "job_created_at": j.created_at,
                            "job_completed_at": j.completed_at,
                            "job_current": j.current,
                            "job_total": j.total,
                            "job_current_file": j.current_file,
                            "is_current": True,
                            "path": cur_path,
                            "code": None,
                            "title": None,
                            "plot": None,
                            "actors": [],
                            "tags": [],
                            "poster_url": None,
                            "fanart_url": None,
                        }
                    )

            if item_rows:
                rows.extend(item_rows)
            elif not cur_path:
                # Fallback: show a placeholder row for the job even if items are not available yet.
                rows.append(
                    {
                        "job_id": j.id,
                        "job_status": j.status,
                        "job_created_at": j.created_at,
                        "job_completed_at": j.completed_at,
                        "job_current": j.current,
                        "job_total": j.total,
                        "job_current_file": j.current_file,
                        "path": j.current_file,
                        "code": None,
                        "title": None,
                        "plot": None,
                        "actors": [],
                        "tags": [],
                        "poster_url": None,
                        "fanart_url": None,
                    }
                )

        # Keep stable ordering: jobs desc, current row first within a job, then by path
        def _sort_key(r: dict):
            return (
                int(r.get("job_id") or 0),
                1 if r.get("is_current") else 0,
                str(r.get("path") or ""),
            )

        rows.sort(key=_sort_key, reverse=True)
        return rows

    def _items_path(self, job_id: int) -> str:
        return os.path.join(self._items_dir, f"items_{int(job_id)}.json")

    def _persist_items_to_disk(self, job_id: int, items: list[dict]) -> None:
        try:
            p = self._items_path(job_id)
            tmp = p + ".tmp"
            Path(tmp).write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, p)
        except Exception:
            return

    def _load_items_from_disk(self, job_id: int) -> list[dict] | None:
        try:
            p = self._items_path(job_id)
            if not os.path.exists(p):
                return None
            raw = Path(p).read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
            return list(data) if isinstance(data, list) else None
        except Exception:
            return None

    def get_job(self, job_id: int) -> dict | None:
        with self._lock:
            job = self._jobs.get(int(job_id))
            return job.__dict__ if job else None

    def _log_path(self, job_id: int) -> str:
        return os.path.join(self._logs_dir, f"scrape_{job_id}.log")

    def _append_log(self, job_id: int, line: str) -> None:
        p = self._log_path(job_id)
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        Path(p).write_text("", encoding="utf-8") if not os.path.exists(p) else None
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{ts} {line}\n")

        # Also mirror to server console logs so users can see meaningful debug output
        # without opening the per-job log viewer.
        try:
            logger.info(f"[scrape {job_id}] {line}")
        except Exception:
            pass

    def read_log(self, job_id: int, offset: int = 0, max_bytes: int = 65536) -> dict:
        path = self._log_path(job_id)
        if not os.path.exists(path):
            return {"exists": False, "text": "", "next_offset": 0}

        try:
            size = os.path.getsize(path)
            safe_offset = max(0, min(int(offset or 0), size))
            with open(path, "rb") as f:
                f.seek(safe_offset)
                data = f.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
            return {"exists": True, "text": text, "next_offset": safe_offset + len(data)}
        except Exception as e:
            return {"exists": True, "text": f"[read log error] {e}\n", "next_offset": offset}

    def read_item_log(self, job_id: int, filename: str, max_lines: int = 2000) -> dict:
        """Return the log slice for a single video inside a scrape job.

        The slice is delimited by runner markers like: === [i/total] <filename> ===
        """
        path = self._log_path(job_id)
        if not os.path.exists(path):
            return {"exists": False, "text": "", "filename": filename}

        target = os.path.basename(str(filename or "").strip())
        if not target:
            return {"exists": True, "text": "", "filename": filename}

        marker_re = re.compile(r"===\s*\[(\d+)\/(\d+)\]\s+(.+?)\s*===")
        lines_out: list[str] = []
        in_section = False
        found = False

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw in f:
                    # Stored format: "YYYY-MM-DD HH:MM:SS <msg>\n"
                    msg = raw[20:] if len(raw) >= 20 and raw[19] == " " else raw
                    m = marker_re.search(msg)
                    if m:
                        name = str(m.group(3) or "").strip()
                        name_base = os.path.basename(name)
                        if in_section and found:
                            break
                        in_section = (name_base == target) or (name == target)
                        if in_section:
                            found = True
                            lines_out.append(raw)
                        continue

                    if in_section:
                        lines_out.append(raw)
                        if max_lines and len(lines_out) >= int(max_lines):
                            break

            return {"exists": True, "text": "".join(lines_out), "filename": filename}
        except Exception as e:
            return {"exists": True, "text": f"[read item log error] {e}\n", "filename": filename}

    def delete_job_logs(self, job_id: int) -> None:
        p = self._log_path(job_id)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    def cleanup_logs(self) -> dict:
        """Delete scrape job log files on disk.

        Only removes task_logs/scrape_*.log. It does NOT delete job/item snapshots
        (scrape_jobs.json, scrape_items/items_*.json) so history can remain.
        """
        deleted = 0
        truncated_running = 0
        errors = 0

        with self._lock:
            running_ids = {str(j.id) for j in self._jobs.values() if j.status in {"Running", "Starting"}}

        try:
            for name in os.listdir(self._logs_dir):
                if not (name.startswith("scrape_") and name.endswith(".log")):
                    continue
                job_id_str = name[len("scrape_") : -len(".log")]
                if job_id_str in running_ids:
                    # Keep job running; just truncate so UI sees cleared immediately.
                    path = os.path.join(self._logs_dir, name)
                    try:
                        with open(path, "w", encoding="utf-8"):
                            pass
                        truncated_running += 1
                    except Exception:
                        errors += 1
                    continue
                path = os.path.join(self._logs_dir, name)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        deleted += 1
                except Exception:
                    errors += 1
        except Exception:
            errors += 1

        return {
            "status": "success" if errors == 0 else "partial",
            "deleted": deleted,
            "truncated_running": truncated_running,
            "errors": errors,
        }

    def clear_history(self) -> dict:
        """Clear ALL scrape history immediately.

        This removes:
        - In-memory jobs/items
        - Persisted job snapshots (task_logs/scrape_jobs.json)
        - Persisted item snapshots (task_logs/scrape_items/items_*.json)
        - Per-job log files (task_logs/scrape_*.log)

        Safety: refuses to run if a scrape job is currently Running/Starting.
        """
        with self._lock:
            if any(j.status in {"Running", "Starting"} for j in self._jobs.values()):
                return {"status": "error", "message": "cannot clear history while a job is running"}
            self._jobs = {}
            self._items = {}
            self._next_id = 1

        deleted_files = 0
        errors = 0

        # Remove persisted jobs snapshot
        try:
            if os.path.exists(self._jobs_path):
                os.remove(self._jobs_path)
                deleted_files += 1
        except Exception:
            errors += 1

        # Remove per-job items snapshots
        try:
            if os.path.isdir(self._items_dir):
                for name in os.listdir(self._items_dir):
                    if not (name.startswith("items_") and name.endswith(".json")):
                        continue
                    p = os.path.join(self._items_dir, name)
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                            deleted_files += 1
                    except Exception:
                        errors += 1
        except Exception:
            errors += 1

        # Remove scrape log files
        try:
            for name in os.listdir(self._logs_dir):
                if not (name.startswith("scrape_") and name.endswith(".log")):
                    continue
                p = os.path.join(self._logs_dir, name)
                try:
                    if os.path.exists(p):
                        os.remove(p)
                        deleted_files += 1
                except Exception:
                    errors += 1
        except Exception:
            errors += 1

        return {
            "status": "success" if errors == 0 else "partial",
            "deleted_files": deleted_files,
            "errors": errors,
        }

    def start_job(self, directory: str, ignore_min_age: bool = False) -> dict:
        directory = directory.strip()
        if not directory:
            return {"status": "error", "message": "scrape_dir is empty"}
        if not os.path.isdir(directory):
            return {"status": "error", "message": "scrape_dir is not a directory"}

        # Best-effort: initialize current_file early so UI can show code immediately.
        # Full scan + total is computed in worker.
        min_age_sec = 0.0 if ignore_min_age else self._get_scrape_min_age_sec()
        first_file = self._peek_first_video(directory, min_age_sec=min_age_sec)

        with self._lock:
            job_id = self._next_id
            self._next_id += 1
            job = ScrapeJob(
                id=job_id,
                directory=directory,
                status="Starting",
                created_at=time.time(),
                ignore_min_age=ignore_min_age,
            )
            if first_file:
                job.current_file = first_file
            self._jobs[job_id] = job
            self._items[job_id] = []
            self._persist_jobs_to_disk_locked()

        self._append_log(job_id, f"Start scraping: {directory} (ignore_min_age={ignore_min_age})")

        t = threading.Thread(target=self._worker, args=(job_id,), daemon=True)
        t.start()
        return {"status": "success", "job_id": job_id}

    def _worker(self, job_id: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return

        cfg = load_config()

        # Pre-scan eligible files so UI has total/current_file early.
        try:
            min_age_sec = 0.0 if job.ignore_min_age else self._get_scrape_min_age_sec(cfg)
            files = self._scan_eligible_videos(job.directory, min_age_sec=min_age_sec)
            first = str(files[0]) if files else None
            total = len(files)
            with self._lock:
                job.total = total
                job.current = int(job.current or 0)
                if (not job.current_file) and first:
                    job.current_file = first
                job.status = "Running"
                self._persist_jobs_to_disk_locked()
        except Exception:
            # Even if scan fails, continue; runner will log/scan later.
            with self._lock:
                job.status = "Running"
                self._persist_jobs_to_disk_locked()

        try:
            from mr_banana.scraper.crawlers.javbus import JavbusConfig, JavbusCrawler
            from mr_banana.scraper.crawlers.javdb import JavdbConfig, JavdbCrawler
            from mr_banana.scraper.crawlers.dmm import DmmConfig, DmmCrawler
            from mr_banana.scraper.crawlers.javtrailers import JavtrailersConfig, JavtrailersCrawler
            from mr_banana.scraper.crawlers.theporndb import ThePornDBConfig, ThePornDBCrawler
            from mr_banana.scraper.runner import scrape_directory
        except Exception as e:
            self._append_log(job_id, f"Scrape failed: init error: {e}")
            with self._lock:
                j = self._jobs.get(job_id)
                if j:
                    j.status = "Failed"
                    j.completed_at = time.time()
                    self._persist_jobs_to_disk_locked()
            return

        use_proxy = bool(getattr(cfg, "scrape_use_proxy", False))
        proxy_url = str(getattr(cfg, "scrape_proxy_url", "") or "").strip() if use_proxy else ""

        def job_log(message: str) -> None:
            self._append_log(job_id, message)

        def _cfg_list(name: str) -> list[str]:
            v = getattr(cfg, name, None)
            return list(v or []) if isinstance(v, list) else []

        field_sources: dict[str, list[str]] = {
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

        sources_set: set[str] = set()
        for lst in field_sources.values():
            for s in lst or []:
                sources_set.add(str(s))

        # Safety: if somehow nothing is enabled, fall back to legacy scrape_sources.
        if not sources_set:
            sources_set = set(list(getattr(cfg, "scrape_sources", ["javbus", "dmm", "javdb"]) or ["javbus", "dmm", "javdb"]))

        # Stable crawler creation order: javbus -> dmm -> javdb -> javtrailers -> theporndb.
        sources = [s for s in ["javbus", "dmm", "javdb", "javtrailers", "theporndb"] if s in sources_set]
        crawlers = []
        for s in sources:
            if s == "javdb":
                crawlers.append(
                    JavdbCrawler(
                        JavdbConfig(
                            cookie=getattr(cfg, "javdb_cookie", "") or "",
                            request_delay_sec=float(getattr(cfg, "scrape_javdb_delay_sec", 0.0) or 0.0),
                            proxy_url=proxy_url,
                        ),
                        log_fn=job_log,
                    )
                )
            elif s == "javbus":
                crawlers.append(
                    JavbusCrawler(
                        JavbusConfig(
                            cookie=getattr(cfg, "javbus_cookie", "") or "",
                            request_delay_sec=float(getattr(cfg, "scrape_javbus_delay_sec", 0.0) or 0.0),
                            proxy_url=proxy_url,
                        ),
                        log_fn=job_log,
                    )
                )
            elif s == "dmm":
                crawlers.append(
                    DmmCrawler(
                        DmmConfig(
                            request_delay_sec=float(getattr(cfg, "scrape_javdb_delay_sec", 0.0) or 0.0),
                            proxy_url=proxy_url,
                        ),
                        log_fn=job_log,
                    )
                )
            elif s == "javtrailers":
                crawlers.append(
                    JavtrailersCrawler(
                        JavtrailersConfig(
                            request_delay_sec=float(getattr(cfg, "scrape_javdb_delay_sec", 0.0) or 0.0),
                            proxy_url=proxy_url,
                        ),
                        log_fn=job_log,
                    )
                )
            elif s == "theporndb":
                crawlers.append(
                    ThePornDBCrawler(
                        ThePornDBConfig(
                            api_token=str(getattr(cfg, "theporndb_api_token", "") or ""),
                            request_delay_sec=float(getattr(cfg, "scrape_javdb_delay_sec", 0.0) or 0.0),
                            proxy_url=proxy_url,
                        ),
                        log_fn=job_log,
                    )
                )

        if not crawlers:
            self._append_log(job_id, "Scrape failed: no sources enabled")
            with self._lock:
                job.status = "Failed"
                job.completed_at = time.time()
            return

        def progress_cb(current: int, total: int, current_file: str):
            with self._lock:
                j = self._jobs.get(job_id)
                if not j:
                    return
                j.current = current
                j.total = total
                j.current_file = current_file

        try:
            out_dir_raw = str(getattr(cfg, "scrape_output_dir", "") or "").strip()
            out_root = Path(out_dir_raw).expanduser().resolve() if out_dir_raw else None

            def to_item(r) -> dict:
                m = r.merged
                data = m.data or {}

                preview_local_urls: list[str] = []
                poster_local_url: str | None = None
                fanart_local_url: str | None = None
                try:
                    pdir = Path(str(r.path)).expanduser().resolve().parent
                    video_stem = Path(str(r.path)).stem

                    # Determine the root directory for generating relative URLs
                    # Use out_root if available and pdir is under it, otherwise use pdir's parent
                    url_root = None
                    if out_root and out_root.exists() and out_root.is_dir():
                        try:
                            # Check if pdir is under out_root
                            pdir.relative_to(out_root)
                            url_root = out_root
                        except ValueError:
                            # pdir is not under out_root, use pdir itself as root
                            url_root = pdir
                    else:
                        url_root = pdir

                    if url_root and pdir.exists() and pdir.is_dir():
                        # Find local poster
                        for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                            poster_path = pdir / f"{video_stem}-poster{ext}"
                            if poster_path.exists() and poster_path.is_file():
                                try:
                                    rel = str(poster_path.relative_to(url_root))
                                    poster_local_url = f"/api/library/file?rel={quote(rel)}"
                                except Exception:
                                    pass
                                break

                        # Find local fanart
                        for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                            fanart_path = pdir / f"{video_stem}-fanart{ext}"
                            if fanart_path.exists() and fanart_path.is_file():
                                try:
                                    rel = str(fanart_path.relative_to(url_root))
                                    fanart_local_url = f"/api/library/file?rel={quote(rel)}"
                                except Exception:
                                    pass
                                break

                        # Find local previews - scan directory for preview files
                        # Priority: use preview_files from data, fallback to glob scanning
                        preview_files = data.get("preview_files") or []
                        if not preview_files:
                            # Fallback: scan for preview files in the directory
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

                # Find local trailer file
                trailer_local_url = None
                try:
                    trailer_file = data.get("trailer_file")
                    if trailer_file and pdir:
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

            def item_cb(r) -> None:
                try:
                    it = to_item(r)
                    # Per-movie completion time (so UI can show end time immediately
                    # without waiting for the entire job to finish).
                    it["item_completed_at"] = time.time()
                    with self._lock:
                        cur = list(self._items.get(job_id, []) or [])
                        cur.append(it)
                        self._items[job_id] = cur
                    # Persist incrementally so history remains stable during long-running jobs.
                    # (Previously we only persisted at job end; if frontend polls between items,
                    # a transient empty/partial in-memory state could make completed rows appear to "disappear".)
                    try:
                        self._persist_items_to_disk(job_id, cur)
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
                options={
                    "output_dir": getattr(cfg, "scrape_output_dir", "") or "",
                    "structure": getattr(cfg, "scrape_structure", "{actor}/{year}/{code}")
                    or "{actor}/{year}/{code}",
                    "rename": bool(getattr(cfg, "scrape_rename", True)),
                    "copy_source": bool(getattr(cfg, "scrape_copy_source", True)),
                    "existing_action": str(getattr(cfg, "scrape_existing_action", "skip") or "skip"),
                    "threads": int(getattr(cfg, "scrape_threads", 1) or 1),
                    "thread_delay_sec": float(getattr(cfg, "scrape_thread_delay_sec", 0.0) or 0.0),

                    # Safety for auto-trigger runs; manual runs can ignore min-age.
                    "min_age_sec": 0.0
                    if job.ignore_min_age
                    else float(getattr(cfg, "scrape_trigger_watch_min_age_sec", 0.0) or 0.0),

                    "write_nfo": bool(getattr(cfg, "scrape_write_nfo", True)),
                    "download_poster": bool(getattr(cfg, "scrape_download_poster", True)),
                    "download_fanart": bool(getattr(cfg, "scrape_download_fanart", True)),
                    "download_previews": bool(getattr(cfg, "scrape_download_previews", False)),
                    "download_trailer": bool(getattr(cfg, "scrape_download_trailer", False)),
                    "download_subtitle": bool(getattr(cfg, "scrape_download_subtitle", False)),
                    "subtitle_languages": list(getattr(cfg, "scrape_subtitle_languages", []) or []),
                    "preview_limit": int(getattr(cfg, "scrape_preview_limit", 8) or 8),
                    "nfo_fields": list(getattr(cfg, "scrape_nfo_fields", []) or []),

                    # Translation
                    "translate_enabled": bool(getattr(cfg, "scrape_translate_enabled", False)),
                    "translate_provider": str(getattr(cfg, "scrape_translate_provider", "google") or "google"),
                    "translate_target_lang": str(getattr(cfg, "scrape_translate_target_lang", "zh-CN") or "zh-CN"),
                    "translate_base_url": str(getattr(cfg, "scrape_translate_base_url", "") or ""),
                    "translate_api_key": str(getattr(cfg, "scrape_translate_api_key", "") or ""),
                    "translate_email": str(getattr(cfg, "scrape_translate_email", "") or ""),

                    # Network
                    "proxy_url": proxy_url,

                    # Per-field sources used by the merger
                    "field_sources": field_sources,
                },
            )

            # Ensure final ordering is stable after completion.
            try:
                # Keep per-item timestamps recorded during the run.
                with self._lock:
                    existing = list(self._items.get(job_id, []) or [])
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
                with self._lock:
                    self._items[job_id] = final_items
                self._persist_items_to_disk(job_id, final_items)
            except Exception:
                pass

            self._append_log(job_id, "Scrape finished")
            with self._lock:
                job.status = "Completed"
                job.completed_at = time.time()
                self._persist_jobs_to_disk_locked()
        except Exception as e:
            self._append_log(job_id, f"Scrape failed: {e}")
            with self._lock:
                job.status = "Failed"
                job.completed_at = time.time()
                self._persist_jobs_to_disk_locked()


scrape_manager = ScrapeManager()
