from __future__ import annotations

from pathlib import Path


VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v"}


def scan_videos(root_dir: str | Path, recursive: bool = True) -> list[Path]:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []

    it = root.rglob("*") if recursive else root.glob("*")
    files: list[Path] = []
    for p in it:
        if not p.is_file():
            continue
        if p.suffix.lower() in VIDEO_EXTS:
            files.append(p)

    files.sort(key=lambda x: x.as_posix().lower())
    return files
