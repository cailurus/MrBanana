"""
Security utilities for path validation and media root management
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from fastapi import HTTPException

from mr_banana.utils.config import load_config


def is_safe_path(base_path: str | Path, target_path: str | Path) -> bool:
    """
    Check if target_path is safely under base_path (no path traversal).
    
    Args:
        base_path: The allowed base directory
        target_path: The path to validate
        
    Returns:
        True if target_path is safely under base_path
    """
    try:
        base = Path(os.path.expanduser(str(base_path))).resolve()
        target = Path(os.path.expanduser(str(target_path))).resolve()
        
        # Check if target is under base
        return str(target).startswith(str(base) + os.sep) or target == base
    except Exception:
        return False


def validate_path_no_traversal(path: str) -> str:
    """
    Validate that a path doesn't contain path traversal sequences.
    
    Args:
        path: The path to validate
        
    Returns:
        The validated path
        
    Raises:
        HTTPException: If path contains traversal sequences
    """
    if not path:
        raise HTTPException(status_code=400, detail="Path cannot be empty")
    
    # Check for common path traversal patterns
    dangerous_patterns = [
        "..",
        "~",
        "$",
        "`",
        "|",
        ";",
        "&",
        "\x00",  # Null byte
    ]
    
    for pattern in dangerous_patterns:
        if pattern in path:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid path: contains forbidden characters"
            )
    
    return path


def safe_join_path(base_dir: str | Path, *paths: str) -> Path:
    """
    Safely join paths ensuring the result is under base_dir.
    
    Args:
        base_dir: The base directory that must contain the result
        *paths: Path components to join
        
    Returns:
        The joined path
        
    Raises:
        HTTPException: If the resulting path would be outside base_dir
    """
    base = Path(os.path.expanduser(str(base_dir))).resolve()
    
    # Clean and validate each path component
    clean_paths = []
    for p in paths:
        if p:
            validate_path_no_traversal(str(p))
            clean_paths.append(p)
    
    if not clean_paths:
        return base
    
    # Join and resolve
    result = (base / Path(*clean_paths)).resolve()
    
    # Verify result is under base
    if not is_safe_path(base, result):
        raise HTTPException(
            status_code=400,
            detail="Invalid path: access outside allowed directory"
        )
    
    return result


def validate_directory_exists(path: str | Path) -> Path:
    """
    Validate that a directory exists and is accessible.
    
    Args:
        path: Path to validate
        
    Returns:
        Resolved Path object
        
    Raises:
        HTTPException: If path doesn't exist or isn't a directory
    """
    try:
        p = Path(os.path.expanduser(str(path))).resolve()
        
        if not p.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Directory does not exist: {path}"
            )
        
        if not p.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a directory: {path}"
            )
        
        return p
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid directory path: {e}"
        )


# --- Media root helpers (shared by library.py, player_open.py, etc.) ---

_MEDIA_ROOT_ATTRS = ("scrape_output_dir", "scrape_dir", "player_root_dir", "output_dir")


def get_all_media_roots() -> List[Path]:
    """Get all configured media root directories that exist on disk."""
    cfg = load_config()
    roots: List[Path] = []
    for attr in _MEDIA_ROOT_ATTRS:
        dir_str = str(getattr(cfg, attr, "") or "").strip()
        if not dir_str:
            continue
        root = Path(os.path.expanduser(dir_str))
        if root.exists() and root.is_dir() and root not in roots:
            roots.append(root)
    return roots


def get_library_root() -> Path | None:
    """Get the primary library root (player_root_dir > scrape_output_dir)."""
    cfg = load_config()
    root_dir = (
        str(getattr(cfg, "player_root_dir", "") or "").strip()
        or str(getattr(cfg, "scrape_output_dir", "") or "").strip()
    )
    if not root_dir:
        return None
    root = Path(os.path.expanduser(root_dir))
    if not root.exists() or not root.is_dir():
        return None
    return root


def is_path_under_roots(file_path: str | Path, roots: List[Path]) -> bool:
    """Check if file_path is under any of the given root directories."""
    try:
        resolved = Path(file_path).resolve()
        for root in roots:
            root_resolved = root.resolve()
            if resolved == root_resolved or root_resolved in resolved.parents:
                return True
        return False
    except Exception:
        return False
