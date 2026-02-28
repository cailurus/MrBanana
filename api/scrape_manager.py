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
        except Exception as e:
            logger.warning(f"Failed to restore scrape jobs from disk: {e}")
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
        except Exception as e:
            logger.warning(f"Failed to persist scrape jobs to disk: {e}")
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
                mode = cfg.scrape_trigger_mode
                if mode not in {"manual", "interval", "watch"}:
                    mode = "manual"

                # Never auto-start if a job is running.
                if self._has_running_job():
                    time.sleep(1.0)
                    continue

                scrape_dir = (cfg.scrape_dir or "").strip()
                if not scrape_dir or not os.path.isdir(scrape_dir):
                    time.sleep(2.0)
                    continue

                now = time.time()

                if mode == "interval":
                    interval_sec = max(30, int(cfg.scrape_trigger_interval_sec or 3600))
                    if now - float(self._auto_last_trigger_at or 0.0) >= float(interval_sec):
                        res = self.start_job(scrape_dir)
                        if res.get("status") == "success":
                            self._auto_last_trigger_at = now
                    time.sleep(1.0)
                    continue

                if mode == "watch":
                    poll_sec = max(2.0, min(float(cfg.scrape_trigger_watch_poll_sec or 10.0), 120.0))
                    min_age_sec = float(cfg.scrape_trigger_watch_min_age_sec or 300.0)
                    quiet_sec = max(5.0, min(float(cfg.scrape_trigger_watch_quiet_sec or 30.0), 600.0))

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
            except Exception as e:
                logger.debug(f"Auto-trigger loop error: {e}")
                time.sleep(2.0)

    def get_config(self) -> dict:
        cfg = load_config()
        return {
            "scrape_dir": cfg.scrape_dir,
            "scrape_use_proxy": bool(cfg.scrape_use_proxy),
            "scrape_proxy_url": cfg.scrape_proxy_url or "",
            "scrape_output_dir": cfg.scrape_output_dir or "",
            "scrape_structure": cfg.scrape_structure or "{actor}/{year}/{code}",
            "scrape_rename": bool(cfg.scrape_rename),
            "scrape_copy_source": bool(cfg.scrape_copy_source),
            "scrape_existing_action": cfg.scrape_existing_action or "skip",
            "scrape_threads": int(cfg.scrape_threads or 1),
            "scrape_thread_delay_sec": float(cfg.scrape_thread_delay_sec or 0.0),
            "scrape_javdb_delay_sec": float(cfg.scrape_javdb_delay_sec or 0.0),
            "scrape_javbus_delay_sec": float(cfg.scrape_javbus_delay_sec or 0.0),
            "scrape_sources": list(cfg.scrape_sources or []),
            "scrape_sources_fallback": list(cfg.scrape_sources_fallback or []),
            "scrape_sources_title": list(cfg.scrape_sources_title or []),
            "scrape_sources_plot": list(cfg.scrape_sources_plot or []),
            "scrape_sources_actors": list(cfg.scrape_sources_actors or []),
            "scrape_sources_tags": list(cfg.scrape_sources_tags or []),
            "scrape_sources_release": list(cfg.scrape_sources_release or []),
            "scrape_sources_runtime": list(cfg.scrape_sources_runtime or []),
            "scrape_sources_directors": list(cfg.scrape_sources_directors or []),
            "scrape_sources_series": list(cfg.scrape_sources_series or []),
            "scrape_sources_studio": list(cfg.scrape_sources_studio or []),
            "scrape_sources_publisher": list(cfg.scrape_sources_publisher or []),
            "scrape_sources_trailer": list(cfg.scrape_sources_trailer or []),
            "scrape_sources_rating": list(cfg.scrape_sources_rating or []),
            "scrape_sources_poster": list(cfg.scrape_sources_poster or []),
            "scrape_sources_fanart": list(cfg.scrape_sources_fanart or []),
            "scrape_sources_previews": list(cfg.scrape_sources_previews or []),
            "scrape_write_nfo": bool(cfg.scrape_write_nfo),
            "scrape_download_poster": bool(cfg.scrape_download_poster),
            "scrape_download_fanart": bool(cfg.scrape_download_fanart),
            "scrape_download_previews": bool(cfg.scrape_download_previews),
            "scrape_download_trailer": bool(cfg.scrape_download_trailer),
            "scrape_download_subtitle": bool(cfg.scrape_download_subtitle),
            "scrape_subtitle_languages": list(cfg.scrape_subtitle_languages or []),
            "scrape_preview_limit": int(cfg.scrape_preview_limit or 8),
            "scrape_nfo_fields": list(cfg.scrape_nfo_fields or []),
            "scrape_translate_enabled": bool(cfg.scrape_translate_enabled),
            "scrape_translate_provider": cfg.scrape_translate_provider or "google",
            "scrape_translate_target_lang": cfg.scrape_translate_target_lang or "zh-CN",
            "scrape_translate_base_url": cfg.scrape_translate_base_url or "",
            "scrape_translate_api_key": cfg.scrape_translate_api_key or "",
            "scrape_translate_email": cfg.scrape_translate_email or "",
            "scrape_trigger_mode": cfg.scrape_trigger_mode or "manual",
            "scrape_trigger_interval_sec": int(cfg.scrape_trigger_interval_sec or 3600),
            "scrape_trigger_watch_poll_sec": float(cfg.scrape_trigger_watch_poll_sec or 10.0),
            "scrape_trigger_watch_min_age_sec": float(cfg.scrape_trigger_watch_min_age_sec or 300.0),
            "scrape_trigger_watch_quiet_sec": float(cfg.scrape_trigger_watch_quiet_sec or 30.0),
            "theporndb_api_token": cfg.theporndb_api_token or "",
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

    @staticmethod
    def _placeholder_row(job: "ScrapeJob", *, path: str | None = None, is_current: bool = False) -> dict:
        """Create a placeholder row for a job that has no item data yet."""
        row: dict = {
            "job_id": job.id,
            "job_status": job.status,
            "job_created_at": job.created_at,
            "job_completed_at": job.completed_at,
            "job_current": job.current,
            "job_total": job.total,
            "job_current_file": job.current_file,
            "path": path or job.current_file,
            "code": None,
            "title": None,
            "plot": None,
            "actors": [],
            "tags": [],
            "poster_url": None,
            "fanart_url": None,
        }
        if is_current:
            row["is_current"] = True
        return row

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
                    rows.append(self._placeholder_row(j, path=cur_path, is_current=True))

            if item_rows:
                rows.extend(item_rows)
            elif not cur_path:
                # Fallback: show a placeholder row for the job even if items are not available yet.
                rows.append(self._placeholder_row(j))

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
        except Exception as e:
            logger.warning(f"Failed to persist scrape items for job {job_id}: {e}")
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
        from api.scrape_worker import run_scrape_worker
        run_scrape_worker(self, job_id)
