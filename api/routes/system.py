from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
import sys

from curl_cffi import requests
from fastapi import APIRouter, HTTPException, Request

from api.schemas import ChooseDirectoryRequest, OpenPathRequest

router = APIRouter()


def _is_localhost(http_request: Request) -> bool:
    client_host = (http_request.client.host if http_request.client else "")
    return client_host in {"127.0.0.1", "::1"}


def _open_path_native(path: str, reveal: bool = True) -> None:
    p = Path(os.path.expanduser(path)).resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))

    # macOS
    if os.name == "posix" and (os.uname().sysname.lower() == "darwin"):
        if reveal and p.is_file():
            subprocess.check_call(["open", "-R", str(p)])
        else:
            target = p if p.is_dir() else p.parent
            subprocess.check_call(["open", str(target)])
        return

    # Windows
    if os.name == "nt":
        if reveal and p.is_file():
            subprocess.check_call(["explorer", "/select,", str(p)])
        else:
            target = p if p.is_dir() else p.parent
            subprocess.check_call(["explorer", str(target)])
        return

    # Linux / others
    target = p if p.is_dir() else p.parent
    subprocess.check_call(["xdg-open", str(target)])


def _escape_applescript_string(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _choose_directory_native(title: str | None, initial_dir: str | None) -> str | None:
    # macOS: use AppleScript (osascript)
    if os.name == "posix" and (os.uname().sysname.lower() == "darwin"):
        prompt = _escape_applescript_string(title or "请选择目录")
        script = f'POSIX path of (choose folder with prompt "{prompt}")'
        if initial_dir:
            initial_dir = os.path.expanduser(str(initial_dir))
            if os.path.isdir(initial_dir):
                initial_dir_esc = _escape_applescript_string(initial_dir)
                script = (
                    f'POSIX path of (choose folder with prompt "{prompt}" '
                    f'default location POSIX file "{initial_dir_esc}")'
                )
        try:
            out = subprocess.check_output(["osascript", "-e", script], text=True).strip()
            out = out.rstrip("/")
            return out or None
        except subprocess.CalledProcessError:
            return None
        except FileNotFoundError:
            return None

    # Fallback: tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(
            title=title or "Choose Directory",
            initialdir=os.path.expanduser(initial_dir) if initial_dir else os.getcwd(),
        )
        root.destroy()
        if not selected:
            return None
        return os.path.abspath(os.path.expanduser(selected))
    except Exception:
        return None


@router.post("/api/system/choose-directory")
async def choose_directory(payload: ChooseDirectoryRequest, http_request: Request):
    if not _is_localhost(http_request):
        raise HTTPException(status_code=403, detail="choose-directory is only available from localhost")

    selected = _choose_directory_native(payload.title, payload.initial_dir)
    return {"path": selected}


@router.get("/api/system/test-source")
async def test_source(source: str, http_request: Request):
    if not _is_localhost(http_request):
        raise HTTPException(status_code=403, detail="test-source is only available from localhost")


@router.post("/api/system/open-path")
async def open_path(payload: OpenPathRequest, http_request: Request):
    if not _is_localhost(http_request):
        raise HTTPException(status_code=403, detail="open-path is only available from localhost")

    try:
        _open_path_native(payload.path, reveal=bool(payload.reveal if payload.reveal is not None else True))
        return {"ok": True}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="path not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to open path: {e}")

    source_id = (source or "").strip().lower()
    targets: dict[str, str] = {
        "dmm": "https://www.dmm.co.jp/",
        "javtrailers": "https://javtrailers.com/",
        "javbus": "https://www.javbus.com/",
        "javdb": "https://javdb.com/",
        "theporndb": "https://theporndb.net/",
        "subtitlecat": "https://subtitlecat.com/",
    }
    url = targets.get(source_id)
    if not url:
        raise HTTPException(status_code=400, detail="unknown source")

    started = time.time()
    try:
        resp = requests.get(url=url, timeout=8, verify=False, impersonate="chrome")
        ok = bool(getattr(resp, "ok", False))
        status_code = int(getattr(resp, "status_code", 0) or 0)
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "source": source_id,
            "ok": ok,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "url": url,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "source": source_id,
            "ok": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": str(e),
        }
