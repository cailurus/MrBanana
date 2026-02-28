"""
Async utilities for wrapping blocking calls in FastAPI route handlers.

All sync blocking operations (HTTP requests via curl_cffi, file I/O, subprocess)
should be wrapped with run_sync() to avoid blocking the asyncio event loop.
"""
from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar, Callable

T = TypeVar("T")

# Shared executor for blocking route calls.
# 4 workers is sufficient: most blocking calls are I/O-bound.
# DownloadManager and ScrapeManager use their own internal threads.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api-sync")


async def run_sync(fn: Callable[..., T], *args, **kwargs) -> T:
    """Run a synchronous blocking function in the thread pool executor.

    Usage:
        result = await run_sync(blocking_function, arg1, arg2)
        result = await run_sync(obj.method, arg1, kwarg=value)
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        call = functools.partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_executor, call)
    return await loop.run_in_executor(_executor, fn, *args)
