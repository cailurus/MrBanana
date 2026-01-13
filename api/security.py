"""
Security utilities for path validation
"""
import os
from pathlib import Path
from fastapi import HTTPException


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
