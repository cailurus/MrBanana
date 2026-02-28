"""
后台调度器
用于定期执行订阅检查等任务
"""
import threading
from datetime import datetime

from mr_banana.utils.logger import logger
from api.dependencies import get_subscription_manager
from mr_banana.utils.telegram import send_daily_summary

from api.subscription_checker import check_all_subscriptions


class SubscriptionScheduler:
    """订阅检查调度器"""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        """启动调度器"""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Subscription scheduler started")

    def stop(self):
        """停止调度器"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Subscription scheduler stopped")

    def _run_loop(self):
        """运行检查循环"""
        while not self._stop_event.is_set():
            try:
                self._check_and_run()
            except Exception as e:
                logger.error(f"Scheduler check loop error: {e}")

            # Wait for 1 hour or until stop is signaled
            self._stop_event.wait(timeout=3600)

    def _check_and_run(self):
        """检查是否需要运行，如果需要则执行"""
        manager = get_subscription_manager()

        if not manager.should_auto_check():
            return

        logger.info(f"Starting auto subscription check at {datetime.now().isoformat()}")

        try:
            checked_count, updated_count, updates = check_all_subscriptions(send_telegram=False)
            logger.info(f"Auto check completed. {updated_count} subscriptions updated.")

            # Send daily summary via Telegram if enabled
            self._send_telegram_summary(checked_count, updated_count, updates)
        except Exception as e:
            logger.error(f"Error during auto check: {e}")

    def _send_telegram_summary(self, checked_count: int, updated_count: int, updates: list):
        """发送 Telegram 每日汇总"""
        try:
            manager = get_subscription_manager()
            config = manager.get_config()

            if not config.get("telegram_enabled"):
                return

            bot_token = config.get("telegram_bot_token", "")
            chat_id = config.get("telegram_chat_id", "")

            if not bot_token or not chat_id:
                return

            total = len(manager.get_subscriptions(limit=1000))

            send_daily_summary(
                bot_token=bot_token,
                chat_id=chat_id,
                total_subscriptions=total,
                checked_count=checked_count,
                updated_count=updated_count,
                updates=updates,
            )
            logger.info("Telegram notification sent")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")


