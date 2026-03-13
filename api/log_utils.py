"""Shared log-reading helpers used by DownloadManager and ScrapeManager."""
from __future__ import annotations

import os
from typing import Any


def read_log_file(
    path: str | os.PathLike[str],
    offset: int = 0,
    max_bytes: int = 65536,
) -> dict[str, Any]:
    """Read a log file incrementally from *offset*.

    Returns ``{"exists": bool, "text": str, "next_offset": int}``.
    """
    path_str = str(path)
    if not os.path.exists(path_str):
        return {"exists": False, "text": "", "next_offset": 0}

    try:
        size = os.path.getsize(path_str)
        safe_offset = max(0, min(int(offset or 0), size))
        with open(path_str, "rb") as f:
            f.seek(safe_offset)
            data = f.read(max_bytes)
        text = data.decode("utf-8", errors="replace")
        return {"exists": True, "text": text, "next_offset": safe_offset + len(data)}
    except Exception as e:
        return {"exists": True, "text": f"[read log error] {e}\n", "next_offset": offset}
