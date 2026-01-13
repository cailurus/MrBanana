from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .types import MediaInfo


def _ffprobe(path: Path) -> dict | None:
    """Return ffprobe JSON output, or None if ffprobe fails/unavailable."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None

    if proc.returncode != 0:
        return None

    try:
        return json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except Exception:
        return None


def read_media_info(path: str | Path) -> MediaInfo:
    p = Path(path)
    info = MediaInfo(path=p)

    try:
        info.size_bytes = p.stat().st_size
    except Exception:
        info.size_bytes = None

    data = _ffprobe(p)
    if not data:
        return info

    # duration
    try:
        fmt = data.get("format") or {}
        if fmt.get("duration") is not None:
            info.duration_seconds = float(fmt["duration"])
    except Exception:
        pass

    # video stream resolution
    try:
        streams = data.get("streams") or []
        for s in streams:
            if s.get("codec_type") == "video":
                if s.get("width") is not None:
                    info.width = int(s["width"])
                if s.get("height") is not None:
                    info.height = int(s["height"])
                break
    except Exception:
        pass

    return info
