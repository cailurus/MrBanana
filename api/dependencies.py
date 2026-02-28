"""
Centralized dependency injection for FastAPI routes.

All singletons (DownloadManager, ScrapeManager, SubscriptionScheduler,
SubscriptionManager) are created lazily here and injected via Depends().

This replaces module-level global instances, enabling test overrides via
app.dependency_overrides[get_xxx] = lambda: mock_instance.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.manager import DownloadManager
    from api.scrape_manager import ScrapeManager
    from api.scheduler import SubscriptionScheduler
    from mr_banana.utils.subscription import SubscriptionManager


@lru_cache(maxsize=1)
def get_download_manager() -> DownloadManager:
    from api.manager import DownloadManager
    return DownloadManager()


@lru_cache(maxsize=1)
def get_scrape_manager() -> ScrapeManager:
    from api.scrape_manager import ScrapeManager
    return ScrapeManager()


@lru_cache(maxsize=1)
def get_scheduler() -> SubscriptionScheduler:
    from api.scheduler import SubscriptionScheduler
    return SubscriptionScheduler()


@lru_cache(maxsize=1)
def get_subscription_manager() -> SubscriptionManager:
    from mr_banana.utils.subscription import SubscriptionManager
    return SubscriptionManager()
