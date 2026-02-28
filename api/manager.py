from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import threading
import time
from typing import Any

from fastapi import WebSocket

from mr_banana.downloader import MovieDownloader, normalize_jable_input
from mr_banana.utils.network import build_proxies
from mr_banana.utils.history import HistoryManager
from mr_banana.utils.hls import DownloadCancelled
from mr_banana.utils.config import load_config
from mr_banana.utils.logger import logger, MatchTaskIdFilter, set_task_id, clear_task_id, LOGS_DIR


class DownloadManager:
    """Manages download tasks, WebSocket connections, and task history."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._connections_lock = threading.Lock()
        self.active_tasks: dict[str, dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}
        self._log_handlers: dict[str, logging.Handler] = {}
        self._logs_dir = os.path.join(LOGS_DIR, "task_logs")
        os.makedirs(self._logs_dir, exist_ok=True)
        self.history_manager = HistoryManager()
        # 应用重启后，之前处于"准备中/下载中"等未完成任务应标记为 Paused
        self.history_manager.mark_incomplete_as_paused()
        self._downloader: MovieDownloader | None = None
        self._downloader_key: tuple[int, str] | None = None

    def get_active_tasks_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a thread-safe deep copy of active_tasks."""
        with self._tasks_lock:
            return copy.deepcopy(self.active_tasks)

    def _get_downloader(
        self, *, max_workers: int, proxies: dict[str, str] | None
    ) -> MovieDownloader:
        key = (int(max_workers), json.dumps(proxies or {}, sort_keys=True))
        if self._downloader is None or self._downloader_key != key:
            self._downloader = MovieDownloader(max_workers=int(max_workers), proxies=proxies)
            self._downloader_key = key
        return self._downloader

    def _task_log_path(self, task_id: int) -> str:
        return os.path.join(self._logs_dir, f"task_{task_id}.log")

    def _ensure_task_log_handler(self, task_id: int) -> None:
        task_id_str = str(task_id)
        if task_id_str in self._log_handlers:
            return

        path = self._task_log_path(task_id)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(MatchTaskIdFilter(task_id_str))
        logger.addHandler(handler)
        self._log_handlers[task_id_str] = handler

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._connections_lock:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._connections_lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """广播消息给所有连接的客户端"""
        with self._connections_lock:
            connections = list(self.active_connections)
        if not connections:
            return

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                logger.debug("WebSocket connection closed, removing from active list")
                with self._connections_lock:
                    if connection in self.active_connections:
                        self.active_connections.remove(connection)

    def start_download(
        self,
        url: str,
        output_dir: str,
        *,
        scrape_after_download: bool = False,
    ) -> dict[str, Any]:
        """启动下载任务（在独立线程中）"""
        normalized_url, _ = normalize_jable_input(url)
        # active_tasks 的 key 是 task_id，这里按 URL 检查是否已有活动任务
        with self._tasks_lock:
            if any(t.get("url") == normalized_url and t.get("status") not in ("Completed", "Failed") for t in self.active_tasks.values()):
                return {"status": "error", "message": "Task already exists"}

        # 创建任务记录
        task_id = self.history_manager.add_task(normalized_url, status="Preparing", scrape_after_download=bool(scrape_after_download))

        self._ensure_task_log_handler(task_id)

        task_info: dict[str, Any] = {
            "id": task_id,
            "url": normalized_url,
            "status": "Preparing",
            "progress": 0,
            "speed": "0 B/s",
            "total_bytes": 0,
            "error": None,
            "scrape_after_download": bool(scrape_after_download),
            "scrape_job_id": None,
            "scrape_status": "Pending" if scrape_after_download else None,
        }
        with self._tasks_lock:
            self.active_tasks[str(task_id)] = task_info
            self._cancel_events[str(task_id)] = threading.Event()

        # 启动线程
        thread = threading.Thread(
            target=self._download_worker,
            args=(task_id, normalized_url, output_dir, bool(scrape_after_download))
        )
        thread.daemon = True
        thread.start()
        
        return {"status": "success", "task_id": task_id}

    def resume_download(self, task_id: int, output_dir: str) -> dict[str, Any]:
        """恢复一个已存在的任务（复用同一条 history 记录）"""
        task_id_str = str(task_id)
        with self._tasks_lock:
            if task_id_str in self.active_tasks:
                return {"status": "error", "message": "Task already active"}

        task = self.history_manager.get_task(task_id)
        if not task:
            return {"status": "error", "message": "Task not found"}

        if task.get("status") == "Completed":
            return {"status": "error", "message": "Task already completed"}

        url = task.get("url")
        if not url:
            return {"status": "error", "message": "Task url missing"}

        scrape_after_download = bool(task.get("scrape_after_download"))
        scrape_job_id = task.get("scrape_job_id")
        scrape_status = task.get("scrape_status")

        # 更新 DB 状态
        self.history_manager.update_task(task_id, status="Preparing")

        self._ensure_task_log_handler(task_id)

        # 注册内存任务
        with self._tasks_lock:
            self.active_tasks[task_id_str] = {
                "id": task_id,
                "url": url,
                "status": "Preparing",
                "progress": 0,
                "speed": "0 B/s",
                "total_bytes": 0,
                "scrape_after_download": scrape_after_download,
                "scrape_job_id": scrape_job_id,
                "scrape_status": scrape_status,
            }
            self._cancel_events[task_id_str] = threading.Event()

        thread = threading.Thread(
            target=self._download_worker,
            args=(task_id, url, output_dir, scrape_after_download)
        )
        thread.daemon = True
        thread.start()

        return {"status": "success", "task_id": task_id}

    def _watch_scrape_job(self, download_task_id: int, scrape_job_id: int) -> None:
        """Track a scrape job status and reflect it onto the download record."""
        try:
            from api.dependencies import get_scrape_manager
            scrape_manager = get_scrape_manager()
        except Exception:
            logger.warning("Failed to import scrape_manager; cannot watch scrape job %s", scrape_job_id)
            return

        task_id_str = str(download_task_id)
        max_wait_seconds = 86400  # 24 hours
        started = time.time()

        while True:
            if time.time() - started > max_wait_seconds:
                logger.warning(
                    f"Scrape job {scrape_job_id} for task {download_task_id} "
                    f"timed out after {max_wait_seconds}s"
                )
                self.history_manager.update_scrape(download_task_id, scrape_status="Failed")
                if task_id_str in self.active_tasks:
                    self.active_tasks[task_id_str]["scrape_status"] = "Failed"
                return

            try:
                job = scrape_manager.get_job(scrape_job_id)
                if not job:
                    time.sleep(1.0)
                    continue
                status = str(job.get("status") or "")
                if task_id_str in self.active_tasks:
                    self.active_tasks[task_id_str]["scrape_status"] = status
                if status in ("Completed", "Failed"):
                    # Keep download timestamps unchanged.
                    self.history_manager.update_scrape(download_task_id, scrape_status=status)
                    return
                time.sleep(1.0)
            except Exception:
                time.sleep(1.0)

    def pause_task(self, task_id: int) -> dict[str, Any]:
        """暂停任务（协作式取消）。

        说明：当前实现会尽力让下载线程尽快退出；已在进行中的网络请求可能需要一点时间才能返回。
        """
        task_id_str = str(task_id)

        task = self.history_manager.get_task(task_id)
        if not task:
            return {"status": "error", "message": "Task not found"}

        if task.get("status") in ("Completed", "Failed"):
            return {"status": "error", "message": "Task already finished"}

        event = self._cancel_events.get(task_id_str)
        if event:
            event.set()

        # DB 标记为 Paused；保留 active_tasks 以便前端还能看到暂停时的进度
        self.history_manager.update_task(task_id, status="Paused")
        if task_id_str in self.active_tasks:
            self.active_tasks[task_id_str]["status"] = "Paused"

        return {"status": "success", "task_id": task_id}

    def delete_task(self, task_id: int) -> dict[str, Any]:
        """删除任务记录。

        注意：这里只删除 history 记录；不删除已下载文件（避免误删）。
        """
        task_id_str = str(task_id)

        task = self.history_manager.get_task(task_id)
        if not task:
            return {"status": "error", "message": "Task not found"}

        # 如果还在下载，先触发取消并移除活动任务
        event = self._cancel_events.get(task_id_str)
        if event:
            event.set()
        with self._tasks_lock:
            self.active_tasks.pop(task_id_str, None)

        self.history_manager.delete_task(task_id)

        # 删除对应任务日志文件，并关闭 handler
        handler = self._log_handlers.pop(task_id_str, None)
        if handler is not None:
            try:
                logger.removeHandler(handler)
                handler.close()
            except Exception:
                pass

        log_path = self._task_log_path(task_id)
        try:
            if os.path.exists(log_path):
                os.remove(log_path)
        except Exception:
            pass

        return {"status": "success", "task_id": task_id}

    def read_task_log(
        self, task_id: int, offset: int = 0, max_bytes: int = 65536
    ) -> dict[str, Any]:
        """Read task log incrementally.

        offset is in bytes.
        """
        path = self._task_log_path(task_id)
        if not os.path.exists(path):
            return {"exists": False, "text": "", "next_offset": 0}

        try:
            size = os.path.getsize(path)
            safe_offset = max(0, min(int(offset or 0), size))
            with open(path, "rb") as f:
                f.seek(safe_offset)
                data = f.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
            return {
                "exists": True,
                "text": text,
                "next_offset": safe_offset + len(data),
            }
        except Exception as e:
            return {"exists": True, "text": f"[read log error] {e}\n", "next_offset": offset}

    def cleanup_logs(self) -> dict[str, Any]:
        """Delete download task logs on disk.

        - Deletes task_logs/task_*.log for tasks that are not currently active.
        - Closes any file handlers attached to the global logger for those tasks.
        """
        deleted = 0
        truncated_active = 0
        errors = 0

        try:
            with self._tasks_lock:
                active_ids = set(str(k) for k in (self.active_tasks or {}).keys())
        except Exception:
            logger.warning("cleanup_logs: failed to read active task IDs, defaulting to empty set", exc_info=True)
            active_ids = set()

        try:
            for name in os.listdir(self._logs_dir):
                if not (name.startswith("task_") and name.endswith(".log")):
                    continue
                task_id_str = name[len("task_") : -len(".log")]

                if task_id_str in active_ids:
                    # Keep active task log handler intact; just truncate the file.
                    path = os.path.join(self._logs_dir, name)
                    try:
                        # Truncate to empty so UI/next reads show "cleared" immediately.
                        with open(path, "w", encoding="utf-8"):
                            pass
                        truncated_active += 1
                    except Exception:
                        errors += 1
                    continue

                # Detach and close handler if present
                handler = self._log_handlers.pop(task_id_str, None)
                if handler is not None:
                    try:
                        logger.removeHandler(handler)
                        handler.close()
                    except Exception:
                        pass

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
            "truncated_active": truncated_active,
            "errors": errors,
        }

    def clear_history(self) -> dict[str, Any]:
        """Clear ALL download history immediately.

        This removes:
        - SQLite download history rows
        - task_logs/task_*.log files
        - logger file handlers attached for those tasks

        Safety: refuses to run while there are active downloads (Preparing/Downloading).
        """

        # Refuse while any active task is still running/preparing.
        try:
            with self._tasks_lock:
                for t in (self.active_tasks or {}).values():
                    s = str((t or {}).get("status") or "")
                    if s in {"Preparing", "Downloading"}:
                        return {"status": "error", "message": "cannot clear history while downloads are running"}
        except Exception:
            # If we cannot reliably check, be safe.
            logger.warning("clear_history: failed to check active tasks, refusing to proceed", exc_info=True)
            return {"status": "error", "message": "cannot clear history right now"}

        deleted_db_rows = 0
        deleted_logs = 0
        errors = 0

        try:
            deleted_db_rows = int(self.history_manager.clear_all() or 0)
        except Exception:
            logger.warning("clear_history: failed to clear database rows", exc_info=True)
            errors += 1

        # Detach/close all known handlers first.
        try:
            for task_id_str, handler in list((self._log_handlers or {}).items()):
                try:
                    logger.removeHandler(handler)
                    handler.close()
                except Exception:
                    pass
                self._log_handlers.pop(task_id_str, None)
        except Exception:
            logger.warning("clear_history: failed to detach/close log handlers", exc_info=True)
            errors += 1

        # Delete log files on disk.
        try:
            for name in os.listdir(self._logs_dir):
                if not (name.startswith("task_") and name.endswith(".log")):
                    continue
                path = os.path.join(self._logs_dir, name)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        deleted_logs += 1
                except Exception:
                    logger.warning("clear_history: failed to delete log file %s", name, exc_info=True)
                    errors += 1
        except Exception:
            logger.warning("clear_history: failed to list/delete log files", exc_info=True)
            errors += 1

        # Clear any lingering paused/completed tasks in memory (best-effort).
        try:
            with self._tasks_lock:
                self.active_tasks = {}
            self._cancel_events = {}
        except Exception:
            logger.debug("clear_history: failed to clear in-memory task state", exc_info=True)
            pass

        return {
            "status": "success" if errors == 0 else "partial",
            "deleted_db_rows": deleted_db_rows,
            "deleted_logs": deleted_logs,
            "errors": errors,
        }

    def _download_worker(
        self,
        task_id: int,
        url: str,
        output_dir: str,
        scrape_after_download: bool = False,
    ) -> None:
        """后台下载工作线程"""
        task_id_str = str(task_id)
        cancel_event = self._cancel_events.get(task_id_str)

        self._ensure_task_log_handler(task_id)
        set_task_id(task_id_str)
        
        def progress_callback(current, total, speed_str, total_bytes):
            if task_id_str not in self.active_tasks:
                return

            # 如果已经触发取消（暂停），不要再把状态覆盖回 Downloading
            if cancel_event and cancel_event.is_set():
                return
                
            progress = (current / total) * 100 if total > 0 else 0
            
            # 更新内存状态
            self.active_tasks[task_id_str].update({
                "status": "Downloading",
                "progress": progress,
                "speed": speed_str,
                "total_bytes": total_bytes
            })
            
            # 广播进度 (通过 asyncio.run 在线程中调用异步函数是比较麻烦的，
            # 这里我们简化处理：只更新状态，由主循环或定时器推送，或者使用简单的事件循环)
            # 为了简单起见，我们在 FastAPI 中通常使用一个后台任务来推送，
            # 但在线程回调中，我们无法直接 await。
            # 解决方案：将状态写入共享内存，由 FastAPI 的 WebSocket 轮询或通过 queue 通信。
            # 这里我们选择：写入 active_tasks，前端通过 WebSocket 定时轮询或后端定时推送。
            
        try:
            logger.info(f"Task started: id={task_id} url={url}")
            self.history_manager.update_task(task_id, status="Downloading")

            cfg = load_config()
            max_workers = max(1, min(int(cfg.max_download_workers or 16), 128))
            filename_format = cfg.filename_format or "{id}"
            preferred_resolution = cfg.download_resolution or "best"

            use_proxy = bool(cfg.download_use_proxy)
            proxy_url = (cfg.download_proxy_url or "").strip()
            proxies = build_proxies(proxy_url) if use_proxy else None
            
            output_path = self._get_downloader(max_workers=max_workers, proxies=proxies).download(
                url=url,
                output_dir=output_dir,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                filename_format=filename_format,
                preferred_resolution=preferred_resolution,
            )
            
            try:
                stable_output_path = os.path.abspath(output_path) if output_path else None
            except Exception:
                stable_output_path = output_path

            # If user enabled scrape-after-download, mark pending and later attach job id.
            if scrape_after_download:
                self.history_manager.update_task(
                    task_id,
                    status="Completed",
                    output_path=stable_output_path,
                    scrape_after_download=True,
                    scrape_status="Pending",
                )
            else:
                self.history_manager.update_task(task_id, status="Completed", output_path=stable_output_path)

            if task_id_str in self.active_tasks:
                self.active_tasks[task_id_str]["status"] = "Completed"
                self.active_tasks[task_id_str]["progress"] = 100
            logger.info("Task completed")

            # Trigger a scrape job after download completes.
            if scrape_after_download:
                try:
                    from api.dependencies import get_scrape_manager
                    scrape_manager = get_scrape_manager()

                    dir_to_scrape = str(output_dir)
                    if stable_output_path:
                        try:
                            if os.path.isdir(stable_output_path):
                                dir_to_scrape = stable_output_path
                            else:
                                parent = os.path.dirname(stable_output_path)
                                if parent:
                                    dir_to_scrape = parent
                        except Exception:
                            pass

                    if task_id_str in self.active_tasks:
                        self.active_tasks[task_id_str]["scrape_status"] = "Starting"

                    res = scrape_manager.start_job(dir_to_scrape)
                    if res.get("status") == "success":
                        job_id = int(res.get("job_id"))
                        self.history_manager.update_scrape(task_id, scrape_job_id=job_id, scrape_status="Running")
                        if task_id_str in self.active_tasks:
                            self.active_tasks[task_id_str]["scrape_job_id"] = job_id
                            self.active_tasks[task_id_str]["scrape_status"] = "Running"
                        threading.Thread(target=self._watch_scrape_job, args=(task_id, job_id), daemon=True).start()
                    else:
                        msg = str(res.get("message") or "failed")
                        self.history_manager.update_scrape(task_id, scrape_status="Failed")
                        if task_id_str in self.active_tasks:
                            self.active_tasks[task_id_str]["scrape_status"] = "Failed"
                        logger.info(f"Failed to trigger scrape: {msg}")
                except Exception as e:
                    self.history_manager.update_scrape(task_id, scrape_status="Failed")
                    if task_id_str in self.active_tasks:
                        self.active_tasks[task_id_str]["scrape_status"] = "Failed"
                    logger.exception(f"Exception while triggering scrape: {e}")

        except DownloadCancelled:
            # 正常取消：标记为 Paused（不设置 completed_at）
            # If scrape-after-download was enabled, keep it pending.
            if scrape_after_download:
                self.history_manager.update_task(task_id, status="Paused", scrape_after_download=True, scrape_status="Pending")
            else:
                self.history_manager.update_task(task_id, status="Paused")
            if task_id_str in self.active_tasks:
                self.active_tasks[task_id_str]["status"] = "Paused"
            logger.info("Task paused")
                
        except Exception as e:
            logger.exception(f"Download error: {e}")
            if scrape_after_download:
                self.history_manager.update_task(task_id, status="Failed", error=str(e), scrape_after_download=True, scrape_status="Skipped")
            else:
                self.history_manager.update_task(task_id, status="Failed", error=str(e))
            if task_id_str in self.active_tasks:
                self.active_tasks[task_id_str]["status"] = "Failed"
                self.active_tasks[task_id_str]["error"] = str(e)
                if scrape_after_download:
                    self.active_tasks[task_id_str]["scrape_status"] = "Skipped"
            logger.info("Task failed")

        finally:
            # 释放 cancel event
            self._cancel_events.pop(task_id_str, None)
            clear_task_id()
        
        # 任务完成后保留一会儿状态，然后清理（可选）
        # time.sleep(60)
        # if task_id_str in self.active_tasks:
        #    del self.active_tasks[task_id_str]
