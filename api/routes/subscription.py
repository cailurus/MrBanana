"""
Subscription API - Manage magnet link subscriptions
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mr_banana.utils.logger import logger
from mr_banana.utils.subscription import SubscriptionManager

from api.async_utils import run_sync
from api.dependencies import get_subscription_manager
from api.subscription_checker import (
    check_all_subscriptions,
    check_one_subscription,
    create_javdb_crawler,
)

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
async def get_subscriptions(limit: int = Query(100, ge=1, le=1000), manager: SubscriptionManager = Depends(get_subscription_manager)):
    """获取订阅列表"""
    return manager.get_subscriptions(limit=limit)


@router.post("/api/subscription")
async def add_subscription(request: AddSubscriptionRequest, manager: SubscriptionManager = Depends(get_subscription_manager)):
    """添加订阅"""
    crawler = create_javdb_crawler()

    javdb_url = None
    magnet_links = request.magnet_links

    try:
        result = await run_sync(crawler.search_by_code, request.code.strip().upper())
        if result and result.original_url:
            javdb_url = result.original_url
        if result and result.data:
            fetched_magnets = result.data.get("magnet_links", [])
            if fetched_magnets:
                magnet_links = fetched_magnets
    except Exception as e:
        logger.error(f"Failed to fetch JavDB info when adding subscription: {e}")

    try:
        subscription_id = manager.add_subscription(
            code=request.code.strip().upper(),
            magnet_links=magnet_links,
            javdb_url=javdb_url,
        )
        return {"status": "ok", "id": subscription_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/api/subscription/{subscription_id}")
async def delete_subscription(subscription_id: int, manager: SubscriptionManager = Depends(get_subscription_manager)):
    """删除订阅"""
    if manager.remove_subscription(subscription_id):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.post("/api/subscription/{subscription_id}/mark-read")
async def mark_subscription_read(subscription_id: int, manager: SubscriptionManager = Depends(get_subscription_manager)):
    """标记订阅为已读"""
    if manager.mark_as_read(subscription_id):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/api/subscription/config")
async def get_subscription_config(manager: SubscriptionManager = Depends(get_subscription_manager)):
    """获取订阅配置"""
    return manager.get_config()


@router.post("/api/subscription/config")
async def update_subscription_config(request: UpdateConfigRequest, manager: SubscriptionManager = Depends(get_subscription_manager)):
    """更新订阅配置"""
    return manager.update_config(
        check_interval_days=request.check_interval_days,
        telegram_bot_token=request.telegram_bot_token,
        telegram_chat_id=request.telegram_chat_id,
        telegram_enabled=request.telegram_enabled,
    )


@router.post("/api/subscription/telegram/test")
async def test_telegram(manager: SubscriptionManager = Depends(get_subscription_manager)):
    """测试 Telegram 连接"""
    from mr_banana.utils.telegram import TelegramBot
    config = manager.get_config()

    bot_token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")

    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")

    bot = TelegramBot(bot_token, chat_id)
    success, error_msg = await run_sync(bot.test_connection)

    if success:
        return {"status": "ok", "message": "Test message sent"}
    else:
        raise HTTPException(status_code=500, detail=error_msg or "Failed to send test message")


@router.post("/api/subscription/check")
async def check_subscription_updates_endpoint():
    """手动触发检查所有订阅的更新"""
    checked_count, updated_count, _ = await run_sync(check_all_subscriptions, send_telegram=True)
    return {
        "status": "ok",
        "checked_count": checked_count,
        "updated_count": updated_count,
        "message": f"检查了 {checked_count} 个订阅，{updated_count} 个有更新",
    }


@router.post("/api/subscription/{subscription_id}/check")
async def check_single_subscription_endpoint(subscription_id: int, manager: SubscriptionManager = Depends(get_subscription_manager)):
    """检查单个订阅的更新"""
    subscriptions = manager.get_subscriptions(limit=1000)

    sub = None
    for s in subscriptions:
        if s["id"] == subscription_id:
            sub = s
            break

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    crawler = create_javdb_crawler()
    result = await run_sync(check_one_subscription, sub, crawler, manager)

    if result["has_update"]:
        return {"status": "ok", "has_update": True, "new_count": result["new_count"]}
    else:
        return {"status": "ok", "has_update": False, "message": "No new links"}


@router.post("/api/subscription/clear")
async def clear_all_subscriptions(manager: SubscriptionManager = Depends(get_subscription_manager)):
    """清空所有订阅"""
    count = manager.clear_all()
    return {"status": "ok", "deleted": count}
