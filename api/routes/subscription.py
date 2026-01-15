"""
Subscription API - Manage magnet link subscriptions
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from mr_banana.utils.subscription import get_subscription_manager
from mr_banana.scraper.crawlers.javdb import JavdbCrawler, JavdbConfig
from mr_banana.utils.config import load_config

router = APIRouter()


class AddSubscriptionRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    magnet_links: List[dict] = []


class UpdateConfigRequest(BaseModel):
    check_interval_days: Optional[int] = Field(None, ge=1, le=30)
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None


class SubscriptionItem(BaseModel):
    id: int
    code: str
    magnet_links: List[dict] = []
    has_update: bool = False
    update_detail: Optional[str] = None
    created_at: str
    last_checked_at: Optional[str] = None


@router.get("/api/subscription")
async def get_subscriptions(limit: int = 100):
    """获取订阅列表"""
    manager = get_subscription_manager()
    subscriptions = manager.get_subscriptions(limit=limit)
    return subscriptions


@router.post("/api/subscription")
async def add_subscription(request: AddSubscriptionRequest):
    """添加订阅"""
    from datetime import datetime
    
    manager = get_subscription_manager()
    
    # Load proxy config and fetch javdb_url when adding
    cfg = load_config()
    proxy_url = None
    if getattr(cfg, "scrape_use_proxy", False):
        proxy_url = getattr(cfg, "scrape_proxy_url", "") or None
    
    javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
    crawler = JavdbCrawler(cfg=javdb_cfg)
    
    javdb_url = None
    magnet_links = request.magnet_links
    
    try:
        # Try to get the detail page URL and magnet links
        result = crawler.search_by_code(request.code.strip().upper())
        if result and result.original_url:
            javdb_url = result.original_url
        if result and result.data:
            fetched_magnets = result.data.get("magnet_links", [])
            if fetched_magnets:
                magnet_links = fetched_magnets
    except Exception as e:
        print(f"Failed to fetch JavDB info when adding subscription: {e}")
    
    try:
        subscription_id = manager.add_subscription(
            code=request.code.strip().upper(),
            magnet_links=magnet_links,
            javdb_url=javdb_url
        )
        return {"status": "ok", "id": subscription_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/api/subscription/{subscription_id}")
async def delete_subscription(subscription_id: int):
    """删除订阅"""
    manager = get_subscription_manager()
    
    if manager.remove_subscription(subscription_id):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.post("/api/subscription/{subscription_id}/mark-read")
async def mark_subscription_read(subscription_id: int):
    """标记订阅为已读"""
    manager = get_subscription_manager()
    
    if manager.mark_as_read(subscription_id):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/api/subscription/config")
async def get_subscription_config():
    """获取订阅配置"""
    manager = get_subscription_manager()
    return manager.get_config()


@router.post("/api/subscription/config")
async def update_subscription_config(request: UpdateConfigRequest):
    """更新订阅配置"""
    manager = get_subscription_manager()
    return manager.update_config(
        check_interval_days=request.check_interval_days,
        telegram_bot_token=request.telegram_bot_token,
        telegram_chat_id=request.telegram_chat_id,
        telegram_enabled=request.telegram_enabled
    )


@router.post("/api/subscription/telegram/test")
async def test_telegram():
    """测试 Telegram 连接"""
    from mr_banana.utils.telegram import TelegramBot
    
    manager = get_subscription_manager()
    config = manager.get_config()
    
    bot_token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    bot = TelegramBot(bot_token, chat_id)
    success, error_msg = bot.test_connection()
    
    if success:
        return {"status": "ok", "message": "Test message sent"}
    else:
        raise HTTPException(status_code=500, detail=error_msg or "Failed to send test message")


def _check_subscription_updates(send_telegram: bool = False):
    """检查所有订阅的更新（同步函数）
    
    Args:
        send_telegram: 是否发送 Telegram 通知
        
    Returns:
        (checked_count, updated_count): 检查数量和更新数量
    """
    from datetime import datetime
    from mr_banana.utils.telegram import TelegramBot
    
    manager = get_subscription_manager()
    subscriptions = manager.get_subscriptions(limit=1000)
    
    checked_count = len(subscriptions)
    
    if not subscriptions:
        manager.update_last_auto_check()
        return 0, 0
    
    # Load proxy config
    cfg = load_config()
    proxy_url = None
    if getattr(cfg, "scrape_use_proxy", False):
        proxy_url = getattr(cfg, "scrape_proxy_url", "") or None
    
    javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
    crawler = JavdbCrawler(cfg=javdb_cfg)
    
    updated_count = 0
    updated_codes = []
    
    for sub in subscriptions:
        try:
            code = sub["code"]
            old_magnets = sub.get("magnet_links", [])
            old_magnet_urls = {m.get("url") for m in old_magnets if m.get("url")}
            
            # Search JavDB for new magnet links
            result = crawler.search_by_code(code)
            if not result or not result.data:
                # Just update last_checked_at
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
                # Count new links
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
                updated_codes.append(f"{code} (+{added_count})")
            else:
                # No new links, just update last_checked_at
                manager.update_subscription(
                    sub["id"],
                    magnet_links=new_magnets,  # Still update in case data changed
                    has_update=sub.get("has_update", False),  # Keep existing update status
                    update_detail=sub.get("update_detail"),
                    javdb_url=javdb_url
                )
        except Exception as e:
            print(f"Error checking subscription {sub.get('code')}: {e}")
            continue
    
    # Update last auto check time
    manager.update_last_auto_check()
    
    # Send Telegram notification if enabled
    if send_telegram:
        try:
            config = manager.get_config()
            if config.get("telegram_enabled"):
                bot_token = config.get("telegram_bot_token", "")
                chat_id = config.get("telegram_chat_id", "")
                if bot_token and chat_id:
                    bot = TelegramBot(bot_token, chat_id)
                    
                    if updated_count > 0:
                        updates_text = "\n".join([f"• {c}" for c in updated_codes])
                        message = f"🍌 <b>订阅检查完成</b>\n\n" \
                                  f"📊 检查了 {checked_count} 个订阅\n" \
                                  f"✨ 发现 {updated_count} 个有更新：\n{updates_text}"
                    else:
                        message = f"🍌 <b>订阅检查完成</b>\n\n" \
                                  f"📊 检查了 {checked_count} 个订阅\n" \
                                  f"😴 暂无新更新"
                    
                    bot.send_message(message)
        except Exception as e:
            print(f"[Telegram] Failed to send check result: {e}")
    
    return checked_count, updated_count


@router.post("/api/subscription/check")
async def check_subscription_updates():
    """手动触发检查所有订阅的更新"""
    checked_count, updated_count = _check_subscription_updates(send_telegram=True)
    return {
        "status": "ok",
        "checked_count": checked_count,
        "updated_count": updated_count,
        "message": f"检查了 {checked_count} 个订阅，{updated_count} 个有更新"
    }


@router.post("/api/subscription/{subscription_id}/check")
async def check_single_subscription(subscription_id: int):
    """检查单个订阅的更新"""
    from datetime import datetime
    
    manager = get_subscription_manager()
    subscriptions = manager.get_subscriptions(limit=1000)
    
    sub = None
    for s in subscriptions:
        if s["id"] == subscription_id:
            sub = s
            break
    
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Load proxy config
    cfg = load_config()
    proxy_url = None
    if getattr(cfg, "scrape_use_proxy", False):
        proxy_url = getattr(cfg, "scrape_proxy_url", "") or None
    
    javdb_cfg = JavdbConfig(proxy_url=proxy_url or "")
    crawler = JavdbCrawler(cfg=javdb_cfg)
    
    code = sub["code"]
    old_magnets = sub.get("magnet_links", [])
    old_magnet_urls = {m.get("url") for m in old_magnets if m.get("url")}
    
    # Search JavDB for new magnet links
    result = crawler.search_by_code(code)
    if not result or not result.data:
        manager.update_subscription(
            subscription_id,
            magnet_links=old_magnets,
            has_update=sub.get("has_update", False),
            update_detail=sub.get("update_detail")
        )
        return {"status": "ok", "has_update": False, "message": "No data found"}
    
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
            subscription_id,
            magnet_links=new_magnets,
            has_update=True,
            update_detail=update_detail,
            javdb_url=javdb_url,
            new_history_entry=history_entry
        )
        return {"status": "ok", "has_update": True, "new_count": added_count}
    else:
        manager.update_subscription(
            subscription_id,
            magnet_links=new_magnets,
            has_update=sub.get("has_update", False),
            update_detail=sub.get("update_detail"),
            javdb_url=javdb_url
        )
        return {"status": "ok", "has_update": False, "message": "No new links"}


@router.post("/api/subscription/clear")
async def clear_all_subscriptions():
    """清空所有订阅"""
    manager = get_subscription_manager()
    count = manager.clear_all()
    return {"status": "ok", "deleted": count}
