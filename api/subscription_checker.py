"""
Shared subscription check logic.
Used by both api/scheduler.py and api/routes/subscription.py.
"""
from __future__ import annotations

from datetime import datetime

from mr_banana.scraper.crawlers.javdb import JavdbCrawler, JavdbConfig
from mr_banana.utils.config import load_config
from mr_banana.utils.logger import logger
from api.dependencies import get_subscription_manager


def create_javdb_crawler(log_fn=None) -> JavdbCrawler:
    """Create a JavdbCrawler using proxy config from AppConfig."""
    cfg = load_config()
    proxy_url = cfg.scrape_proxy_url if cfg.scrape_use_proxy else ""
    javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
    return JavdbCrawler(cfg=javdb_cfg, log_fn=log_fn)


def check_one_subscription(
    sub: dict,
    crawler: JavdbCrawler,
    manager=None,
) -> dict:
    """Check a single subscription for magnet link updates.

    Returns:
        Dict with keys: has_update (bool), new_count (int), error (str|None).
        Side effect: updates the subscription via manager.
    """
    if manager is None:
        manager = get_subscription_manager()

    code = sub["code"]
    old_magnets = sub.get("magnet_links", [])
    old_magnet_urls = {m.get("url") for m in old_magnets if m.get("url")}

    result = crawler.search_by_code(code)
    if not result or not result.data:
        manager.update_subscription(
            sub["id"],
            magnet_links=old_magnets,
            has_update=sub.get("has_update", False),
            update_detail=sub.get("update_detail"),
        )
        return {"has_update": False, "new_count": 0, "error": None}

    new_magnets = result.data.get("magnet_links", [])
    new_magnet_urls = {m.get("url") for m in new_magnets if m.get("url")}
    javdb_url = result.original_url or sub.get("javdb_url")
    added_urls = new_magnet_urls - old_magnet_urls

    if added_urls:
        added_count = len(added_urls)
        update_detail = f"+{added_count} 个新链接"
        new_links_info = [m for m in new_magnets if m.get("url") in added_urls]
        history_entry = {
            "time": datetime.now().isoformat(),
            "count": added_count,
            "links": new_links_info,
        }
        manager.update_subscription(
            sub["id"],
            magnet_links=new_magnets,
            has_update=True,
            update_detail=update_detail,
            javdb_url=javdb_url,
            new_history_entry=history_entry,
        )
        return {"has_update": True, "new_count": added_count, "error": None}
    else:
        manager.update_subscription(
            sub["id"],
            magnet_links=new_magnets,
            has_update=sub.get("has_update", False),
            update_detail=sub.get("update_detail"),
            javdb_url=javdb_url,
        )
        return {"has_update": False, "new_count": 0, "error": None}


def check_all_subscriptions(
    send_telegram: bool = False,
) -> tuple[int, int, list[dict]]:
    """Check all subscriptions for updates.

    Returns:
        (checked_count, updated_count, updates_list)
    """
    manager = get_subscription_manager()
    subscriptions = manager.get_subscriptions(limit=1000)
    checked_count = len(subscriptions)

    if not subscriptions:
        manager.update_last_auto_check()
        return 0, 0, []

    crawler = create_javdb_crawler()
    updated_count = 0
    updates: list[dict] = []

    for sub in subscriptions:
        try:
            result = check_one_subscription(sub, crawler, manager)
            if result["has_update"]:
                updated_count += 1
                updates.append({
                    "code": sub["code"],
                    "new_count": result["new_count"],
                })
        except Exception as e:
            logger.error(f"Error checking subscription {sub.get('code')}: {e}")
            continue

    manager.update_last_auto_check()

    if send_telegram:
        _send_telegram_if_enabled(manager, checked_count, updated_count, updates)

    return checked_count, updated_count, updates


def _send_telegram_if_enabled(
    manager, checked_count: int, updated_count: int, updates: list[dict]
) -> None:
    """Send Telegram notification if configured."""
    try:
        from mr_banana.utils.telegram import TelegramBot

        config = manager.get_config()
        if not config.get("telegram_enabled"):
            return
        bot_token = config.get("telegram_bot_token", "")
        chat_id = config.get("telegram_chat_id", "")
        if not bot_token or not chat_id:
            return

        bot = TelegramBot(bot_token, chat_id)
        if updated_count > 0:
            codes_text = "\n".join(
                f"  * {u['code']} (+{u['new_count']})" for u in updates
            )
            message = (
                f"<b>Mr. Banana 订阅检查完成</b>\n\n"
                f"检查了 {checked_count} 个订阅\n"
                f"发现 {updated_count} 个有更新:\n{codes_text}"
            )
        else:
            message = (
                f"<b>Mr. Banana 订阅检查完成</b>\n\n"
                f"检查了 {checked_count} 个订阅\n"
                f"暂无新更新"
            )
        bot.send_message(message)
    except Exception as e:
        logger.error(f"Failed to send Telegram check result: {e}")
