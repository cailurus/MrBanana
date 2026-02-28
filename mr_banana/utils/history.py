"""
下载历史记录管理模块
"""
import sqlite3
import os
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional, Generator

# 数据库文件存放在项目根目录的 data/ 目录下
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "mr_banana_history.db")


class HistoryManager:
    """下载历史记录管理器
    
    使用线程安全的连接池管理 SQLite 连接，避免并发问题。
    """

    def __init__(self, db_path: str = DB_FILE):
        # Backward-compatible: if new DB doesn't exist but the old one does,
        # continue using the old file to preserve existing history.
        if db_path == DB_FILE and not os.path.exists(DB_FILE):
            old_paths = [
                os.path.join(DATA_DIR, "banana_history.db"),
                os.path.join(DATA_DIR, "mrjet_history.db"),
                "banana_history.db",  # Legacy root-level paths
                "mrjet_history.db",
                "mr_banana_history.db",
            ]
            for old_path in old_paths:
                if os.path.exists(old_path):
                    db_path = old_path
                    break
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（线程安全）"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=30000")
        return self._local.conn

    @contextmanager
    def _db_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """上下文管理器：获取数据库连接"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    status TEXT,
                    error TEXT,
                    output_path TEXT,
                    scrape_after_download INTEGER DEFAULT 0,
                    scrape_job_id INTEGER,
                    scrape_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Backward-compatible migrations for existing DBs.
            cursor.execute("PRAGMA table_info(downloads)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "scrape_after_download" not in existing_cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN scrape_after_download INTEGER DEFAULT 0")
            if "scrape_job_id" not in existing_cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN scrape_job_id INTEGER")
            if "scrape_status" not in existing_cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN scrape_status TEXT")
            if "error" not in existing_cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN error TEXT")
            conn.commit()

    def add_task(self, url: str, status: str = "排队中", *, scrape_after_download: bool = False) -> int:
        """添加下载任务"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO downloads (url, status, scrape_after_download, scrape_status, created_at) VALUES (?, ?, ?, ?, ?)",
                (url, status, 1 if scrape_after_download else 0, "Pending" if scrape_after_download else None, datetime.now())
            )
            return cursor.lastrowid

    def update_task(
        self,
        task_id: int,
        status: str,
        title: str = None,
        error: str = None,
        output_path: str = None,
        scrape_after_download: bool = None,
        scrape_job_id: int = None,
        scrape_status: str = None,
    ):
        """更新任务状态"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            updates = ["status = ?"]
            params = [status]

            if title:
                updates.append("title = ?")
                params.append(title)
            if error is not None:
                updates.append("error = ?")
                params.append(error)
            if output_path:
                updates.append("output_path = ?")
                params.append(output_path)

            if scrape_after_download is not None:
                updates.append("scrape_after_download = ?")
                params.append(1 if bool(scrape_after_download) else 0)
            if scrape_job_id is not None:
                updates.append("scrape_job_id = ?")
                params.append(scrape_job_id)
            if scrape_status is not None:
                updates.append("scrape_status = ?")
                params.append(scrape_status)

            if status in ["Completed", "Failed"]:
                updates.append("completed_at = ?")
                params.append(datetime.now())

            params.append(task_id)

            query = f"UPDATE downloads SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

    def update_scrape(
        self,
        task_id: int,
        *,
        scrape_after_download: bool = None,
        scrape_job_id: int = None,
        scrape_status: str = None,
    ) -> None:
        """Update scrape-related fields without touching download status timestamps."""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if scrape_after_download is not None:
                updates.append("scrape_after_download = ?")
                params.append(1 if bool(scrape_after_download) else 0)
            if scrape_job_id is not None:
                updates.append("scrape_job_id = ?")
                params.append(scrape_job_id)
            if scrape_status is not None:
                updates.append("scrape_status = ?")
                params.append(scrape_status)

            if not updates:
                return

            params.append(task_id)
            query = f"UPDATE downloads SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

    def get_task(self, task_id: int) -> Optional[Dict]:
        """根据任务 ID 获取任务记录"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE id = ? LIMIT 1", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_task(self, task_id: int) -> None:
        """删除任务记录"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads WHERE id = ?", (task_id,))

    def get_url_by_output_path(self, output_path: str) -> Optional[str]:
        """根据 output_path 反查原始 URL。

        用于刮削：把本地文件路径映射回下载时的页面 URL。
        """
        if not output_path:
            return None

        candidates = []
        try:
            candidates.append(str(output_path))
            candidates.append(os.path.abspath(str(output_path)))
            try:
                candidates.append(os.path.relpath(str(output_path), os.getcwd()))
            except Exception:
                pass
        except Exception:
            candidates = [output_path]

        # 去重并过滤空值
        uniq = []
        seen = set()
        for c in candidates:
            if not c:
                continue
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)

        with self._db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(uniq))
            cursor.execute(
                f"SELECT url FROM downloads WHERE output_path IN ({placeholders}) ORDER BY id DESC LIMIT 1",
                tuple(uniq),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def mark_incomplete_as_paused(self) -> int:
        """将上次异常退出时遗留的未完成任务标记为 Paused。

        规则：completed_at 为空，且状态不是 Completed/Failed/Paused 的任务都会被置为 Paused。

        Returns:
            int: 被更新的行数
        """
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE downloads
                SET status = 'Paused'
                WHERE completed_at IS NULL
                  AND COALESCE(status, '') NOT IN ('Completed', 'Failed', 'Paused')
                """
            )
            return cursor.rowcount

    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取下载历史"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def clear_all(self) -> int:
        """Clear ALL download history rows.

        Returns:
            int: number of deleted rows (best-effort)
        """
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads")
            deleted = int(cursor.rowcount or 0)
            # Reset AUTOINCREMENT counter if possible.
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'downloads'")
            except Exception:
                pass
            return deleted

    def is_url_completed(self, url: str) -> bool:
        """检查 URL 是否已完成下载"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM downloads WHERE url = ? AND status = 'Completed' LIMIT 1",
                (url,)
            )
            return cursor.fetchone() is not None
