"""
订阅管理模块
用于管理磁力链接订阅，定期检查更新
"""
import sqlite3
import os
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional, Generator

# 数据库文件存放在项目根目录的 data/ 目录下
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
SUBSCRIPTION_DB_FILE = os.path.join(DATA_DIR, "mr_banana_subscription.db")


class SubscriptionManager:
    """订阅管理器
    
    管理磁力链接订阅，支持定期检查更新
    """

    def __init__(self, db_path: str = SUBSCRIPTION_DB_FILE):
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
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    magnet_links TEXT DEFAULT '[]',
                    has_update INTEGER DEFAULT 0,
                    update_detail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TIMESTAMP,
                    javdb_url TEXT,
                    update_history TEXT DEFAULT '[]'
                )
            """)
            
            # 订阅配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscription_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    check_interval_days INTEGER DEFAULT 1,
                    last_auto_check_at TIMESTAMP,
                    telegram_bot_token TEXT DEFAULT '',
                    telegram_chat_id TEXT DEFAULT '',
                    telegram_enabled INTEGER DEFAULT 0
                )
            """)
            
            # 初始化配置
            cursor.execute("""
                INSERT OR IGNORE INTO subscription_config (id, check_interval_days)
                VALUES (1, 1)
            """)
            
            # 添加Telegram字段（如果不存在）
            try:
                cursor.execute("ALTER TABLE subscription_config ADD COLUMN telegram_bot_token TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            try:
                cursor.execute("ALTER TABLE subscription_config ADD COLUMN telegram_chat_id TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE subscription_config ADD COLUMN telegram_enabled INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            # 添加 javdb_url 和 update_history 字段（如果不存在）
            try:
                cursor.execute("ALTER TABLE subscriptions ADD COLUMN javdb_url TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE subscriptions ADD COLUMN update_history TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass
            
            conn.commit()

    def add_subscription(self, code: str, magnet_links: List[Dict] = None, javdb_url: str = None) -> int:
        """添加订阅
        
        Args:
            code: 番号
            magnet_links: 当前的磁力链接列表
            javdb_url: JavDB 详情页 URL
            
        Returns:
            订阅ID
            
        Raises:
            ValueError: 如果番号已存在
        """
        with self._db_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute("SELECT id FROM subscriptions WHERE code = ?", (code.upper(),))
            if cursor.fetchone():
                raise ValueError(f"Subscription for {code} already exists")
            
            magnet_json = json.dumps(magnet_links or [], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO subscriptions (code, magnet_links, created_at, javdb_url, update_history)
                VALUES (?, ?, ?, ?, '[]')
            """, (code.upper(), magnet_json, datetime.now().isoformat(), javdb_url))
            
            return cursor.lastrowid

    def remove_subscription(self, subscription_id: int) -> bool:
        """删除订阅"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
            return cursor.rowcount > 0

    def get_subscriptions(self, limit: int = 100) -> List[Dict]:
        """获取订阅列表"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, code, magnet_links, has_update, update_detail, 
                       created_at, last_checked_at, javdb_url, update_history
                FROM subscriptions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                # 解析 magnet_links JSON
                try:
                    item['magnet_links'] = json.loads(item['magnet_links'] or '[]')
                except json.JSONDecodeError:
                    item['magnet_links'] = []
                # 解析 update_history JSON
                try:
                    item['update_history'] = json.loads(item['update_history'] or '[]')
                except json.JSONDecodeError:
                    item['update_history'] = []
                result.append(item)
            return result

    def get_subscription_by_code(self, code: str) -> Optional[Dict]:
        """通过番号获取订阅"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, code, magnet_links, has_update, update_detail, 
                       created_at, last_checked_at, javdb_url, update_history
                FROM subscriptions
                WHERE code = ?
            """, (code.upper(),))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            item = dict(row)
            try:
                item['magnet_links'] = json.loads(item['magnet_links'] or '[]')
            except json.JSONDecodeError:
                item['magnet_links'] = []
            try:
                item['update_history'] = json.loads(item['update_history'] or '[]')
            except json.JSONDecodeError:
                item['update_history'] = []
            return item

    def update_subscription(self, subscription_id: int, magnet_links: List[Dict], 
                           has_update: bool = False, update_detail: str = None,
                           javdb_url: str = None, new_history_entry: Dict = None) -> bool:
        """更新订阅的磁力链接
        
        Args:
            subscription_id: 订阅ID
            magnet_links: 磁力链接列表
            has_update: 是否有更新
            update_detail: 更新详情描述
            javdb_url: JavDB详情页URL
            new_history_entry: 新的历史记录条目，如果有的话追加到历史中
        """
        with self._db_connection() as conn:
            cursor = conn.cursor()
            magnet_json = json.dumps(magnet_links or [], ensure_ascii=False)
            
            # 如果有新的历史记录条目，需要先获取现有历史并追加
            if new_history_entry:
                cursor.execute("SELECT update_history FROM subscriptions WHERE id = ?", (subscription_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        history = json.loads(row[0] or '[]')
                    except json.JSONDecodeError:
                        history = []
                    history.insert(0, new_history_entry)  # 新记录插入到最前面
                    history_json = json.dumps(history, ensure_ascii=False)
                else:
                    history_json = json.dumps([new_history_entry], ensure_ascii=False)
            else:
                history_json = None
            
            # 构建更新语句
            if javdb_url and history_json:
                cursor.execute("""
                    UPDATE subscriptions 
                    SET magnet_links = ?, has_update = ?, update_detail = ?, last_checked_at = ?,
                        javdb_url = ?, update_history = ?
                    WHERE id = ?
                """, (magnet_json, 1 if has_update else 0, update_detail, 
                      datetime.now().isoformat(), javdb_url, history_json, subscription_id))
            elif javdb_url:
                cursor.execute("""
                    UPDATE subscriptions 
                    SET magnet_links = ?, has_update = ?, update_detail = ?, last_checked_at = ?,
                        javdb_url = ?
                    WHERE id = ?
                """, (magnet_json, 1 if has_update else 0, update_detail, 
                      datetime.now().isoformat(), javdb_url, subscription_id))
            elif history_json:
                cursor.execute("""
                    UPDATE subscriptions 
                    SET magnet_links = ?, has_update = ?, update_detail = ?, last_checked_at = ?,
                        update_history = ?
                    WHERE id = ?
                """, (magnet_json, 1 if has_update else 0, update_detail, 
                      datetime.now().isoformat(), history_json, subscription_id))
            else:
                cursor.execute("""
                    UPDATE subscriptions 
                    SET magnet_links = ?, has_update = ?, update_detail = ?, last_checked_at = ?
                    WHERE id = ?
                """, (magnet_json, 1 if has_update else 0, update_detail, 
                      datetime.now().isoformat(), subscription_id))
            return cursor.rowcount > 0

    def mark_as_read(self, subscription_id: int) -> bool:
        """标记订阅为已读（清除更新提示）"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE subscriptions 
                SET has_update = 0, update_detail = NULL
                WHERE id = ?
            """, (subscription_id,))
            return cursor.rowcount > 0

    def get_config(self) -> Dict:
        """获取订阅配置"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT check_interval_days, last_auto_check_at,
                       telegram_bot_token, telegram_chat_id, telegram_enabled
                FROM subscription_config
                WHERE id = 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                "check_interval_days": 1,
                "last_auto_check_at": None,
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "telegram_enabled": 0
            }

    def update_config(
        self,
        check_interval_days: int = None,
        telegram_bot_token: str = None,
        telegram_chat_id: str = None,
        telegram_enabled: bool = None
    ) -> Dict:
        """更新订阅配置"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if check_interval_days is not None:
                updates.append("check_interval_days = ?")
                params.append(max(1, check_interval_days))
            if telegram_bot_token is not None:
                updates.append("telegram_bot_token = ?")
                params.append(telegram_bot_token)
            if telegram_chat_id is not None:
                updates.append("telegram_chat_id = ?")
                params.append(telegram_chat_id)
            if telegram_enabled is not None:
                updates.append("telegram_enabled = ?")
                params.append(1 if telegram_enabled else 0)
            
            if updates:
                cursor.execute(f"""
                    UPDATE subscription_config
                    SET {', '.join(updates)}
                    WHERE id = 1
                """, params)
            
            return self.get_config()

    def update_last_auto_check(self) -> None:
        """更新最后自动检查时间"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE subscription_config
                SET last_auto_check_at = ?
                WHERE id = 1
            """, (datetime.now().isoformat(),))

    def should_auto_check(self) -> bool:
        """检查是否应该执行自动检查"""
        config = self.get_config()
        last_check = config.get("last_auto_check_at")
        interval_days = config.get("check_interval_days", 1)
        
        if not last_check:
            return True
        
        try:
            last_check_dt = datetime.fromisoformat(last_check)
            now = datetime.now()
            delta = now - last_check_dt
            return delta.days >= interval_days
        except (ValueError, TypeError):
            return True

    def clear_all(self) -> int:
        """清空所有订阅"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions")
            return cursor.rowcount


# 全局单例
_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """获取订阅管理器单例"""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager
