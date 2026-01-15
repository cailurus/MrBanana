"""
后台调度器
用于定期执行订阅检查等任务
"""
import asyncio
import threading
from datetime import datetime
from typing import Callable, Optional

from mr_banana.utils.subscription import get_subscription_manager
from mr_banana.scraper.crawlers.javdb import JavdbCrawler, JavdbConfig
from mr_banana.utils.config import load_config
from mr_banana.utils.telegram import send_daily_summary


class SubscriptionScheduler:
    """订阅检查调度器"""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("[Scheduler] Subscription scheduler started")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] Subscription scheduler stopped")
    
    def _run_loop(self):
        """运行检查循环"""
        while self._running:
            try:
                self._check_and_run()
            except Exception as e:
                print(f"[Scheduler] Error in check loop: {e}")
            
            # Sleep for 1 hour before checking again
            for _ in range(3600):
                if not self._running:
                    break
                import time
                time.sleep(1)
    
    def _check_and_run(self):
        """检查是否需要运行，如果需要则执行"""
        manager = get_subscription_manager()
        
        if not manager.should_auto_check():
            return
        
        print(f"[Scheduler] Starting auto check at {datetime.now().isoformat()}")
        
        try:
            updated_count, updates = self._check_all_subscriptions()
            print(f"[Scheduler] Auto check completed. {updated_count} subscriptions updated.")
            
            # Send Telegram notification if enabled
            self._send_telegram_notification(updated_count, updates)
        except Exception as e:
            print(f"[Scheduler] Error during auto check: {e}")
    
    def _send_telegram_notification(self, updated_count: int, updates: list):
        """发送 Telegram 通知"""
        try:
            manager = get_subscription_manager()
            config = manager.get_config()
            
            if not config.get("telegram_enabled"):
                return
            
            bot_token = config.get("telegram_bot_token", "")
            chat_id = config.get("telegram_chat_id", "")
            
            if not bot_token or not chat_id:
                return
            
            subscriptions = manager.get_subscriptions(limit=1000)
            total = len(subscriptions)
            
            send_daily_summary(
                bot_token=bot_token,
                chat_id=chat_id,
                total_subscriptions=total,
                checked_count=total,
                updated_count=updated_count,
                updates=updates
            )
            print("[Scheduler] Telegram notification sent")
        except Exception as e:
            print(f"[Scheduler] Failed to send Telegram notification: {e}")
    
    def _check_all_subscriptions(self) -> tuple:
        """检查所有订阅的更新
        
        Returns:
            (updated_count, updates): 更新数量和更新详情列表
        """
        manager = get_subscription_manager()
        subscriptions = manager.get_subscriptions(limit=1000)
        
        if not subscriptions:
            manager.update_last_auto_check()
            return 0, []
        
        # Load proxy config
        cfg = load_config()
        proxy_url = None
        if getattr(cfg, "scrape_use_proxy", False):
            proxy_url = getattr(cfg, "scrape_proxy_url", "") or None
        
        javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
        crawler = JavdbCrawler(cfg=javdb_cfg)
        
        updated_count = 0
        updates = []
        
        for sub in subscriptions:
            try:
                code = sub["code"]
                old_magnets = sub.get("magnet_links", [])
                old_magnet_urls = {m.get("url") for m in old_magnets if m.get("url")}
                
                # Search JavDB for new magnet links
                result = crawler.search_by_code(code)
                if not result or not result.data:
                    manager.update_subscription(
                        sub["id"],
                        magnet_links=old_magnets,
                        has_update=sub.get("has_update", False),
                        update_detail=sub.get("update_detail")
                    )
                    continue
                
                new_magnets = result.data.get("magnet_links", [])
                new_magnet_urls = {m.get("url") for m in new_magnets if m.get("url")}
                
                # Get the detail page URL from result
                javdb_url = result.original_url or sub.get("javdb_url")
                
                # Find new links
                added_urls = new_magnet_urls - old_magnet_urls
                
                if added_urls:
                    added_count = len(added_urls)
                    update_detail = f"+{added_count} 个新链接"
                    
                    # Create history entry with new link details
                    new_links_info = [
                        m for m in new_magnets 
                        if m.get("url") in added_urls
                    ]
                    history_entry = {
                        "time": datetime.now().isoformat(),
                        "count": added_count,
                        "links": new_links_info
                    }
                    
                    manager.update_subscription(
                        sub["id"],
                        magnet_links=new_magnets,
                        has_update=True,
                        update_detail=update_detail,
                        javdb_url=javdb_url,
                        new_history_entry=history_entry
                    )
                    updated_count += 1
                    updates.append({
                        "code": code,
                        "new_count": added_count,
                    })
                else:
                    manager.update_subscription(
                        sub["id"],
                        magnet_links=new_magnets,
                        has_update=sub.get("has_update", False),
                        update_detail=sub.get("update_detail"),
                        javdb_url=javdb_url
                    )
            except Exception as e:
                print(f"[Scheduler] Error checking subscription {sub.get('code')}: {e}")
                continue
        
        # Update last auto check time
        manager.update_last_auto_check()
        
        return updated_count, updates


# 全局调度器实例
_scheduler: Optional[SubscriptionScheduler] = None


def get_scheduler() -> SubscriptionScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SubscriptionScheduler()
    return _scheduler


def start_scheduler():
    """启动调度器"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """停止调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
