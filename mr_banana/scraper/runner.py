from __future__ import annotations

from mr_banana.utils.logger import logger
from mr_banana.utils.translate import translate_text

import json
import re
import shutil
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from .file_scanner import scan_videos
from .media_info import read_media_info
from .merger import merge_results
from .types import ScrapeItemResult
from .writers.nfo import NfoWriteOptions, write_nfo
from .crawlers.subtitlecat import SubtitleCatCrawler


def _sanitize_segment(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return "Unknown"
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120] if len(s) > 120 else s


def _extract_year(release: str | None) -> str:
    if not release:
        return "Unknown"
    m = re.search(r"(\d{4})", str(release))
    return m.group(1) if m else "Unknown"


def _avoid_collision(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suf = path.suffix
    parent = path.parent
    for i in range(1, 1000):
        p = parent / f"{stem}-{i}{suf}"
        if not p.exists():
            return p
    return path


def _norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _infer_plot_source(per_file_results, merged_plot_norm: str) -> str:
    if not merged_plot_norm:
        return ""
    for rr in per_file_results:
        try:
            rp = (rr.data or {}).get("plot")
            rp_norm = _norm_ws(rp) if isinstance(rp, str) else ""
            if rp_norm and rp_norm == merged_plot_norm:
                return str(getattr(rr, "source", "") or "")
        except Exception:
            continue
    return ""


def _emit_live_json(
    safe_log,
    *,
    file_path: Path,
    merged,
    per_file_results,
    subtitles: list[Path] | None = None,
) -> None:
    """Emit structured live metadata for real-time UI (best effort)."""
    try:
        data = merged.data or {}
        plot_val = data.get("plot")
        plot_text = plot_val.strip() if isinstance(plot_val, str) else ""
        plot_norm = _norm_ws(plot_text)
        plot_src = _infer_plot_source(per_file_results, plot_norm)

        live = {
            "phase": "merged",
            "file": str(file_path),
            "file_name": str(file_path.name),
            "code": str(merged.external_id or ""),
            "title": str(merged.title or ""),
            "url": str(merged.original_url or ""),
            "hit_sources": [str(getattr(rr, "source", "") or "") for rr in per_file_results],
            "release": data.get("release"),
            "runtime": data.get("runtime"),
            "studio": data.get("studio"),
            "series": data.get("series"),
            "actors": data.get("actors"),
            "tags": data.get("tags"),
            "poster_url": data.get("poster_url") or data.get("cover_url"),
            "fanart_url": data.get("fanart_url"),
            "plot_len": len(plot_text) if plot_text else 0,
            "plot_source": plot_src,
            "plot_preview": plot_norm[:240] if plot_norm else "",
            "subtitles": [str(p.name) for p in (subtitles or [])],
        }
        safe_log("live.json: " + json.dumps(live, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        return


def scrape_directory(
    directory: str | Path,
    crawlers,
    progress_cb=None,
    log_cb=None,
    options: dict | None = None,
    item_cb=None,
) -> list[ScrapeItemResult]:
    """Scrape a directory and write NFO files.

    This is intentionally synchronous; callers can run it in a thread.
    """
    opts = options or {}
    output_dir_raw = str(opts.get("output_dir") or "").strip()
    output_dir = Path(output_dir_raw).expanduser() if output_dir_raw else None
    structure = str(opts.get("structure") or "{actor}/{year}/{code}")
    rename = bool(opts.get("rename", True))
    copy_source = bool(opts.get("copy_source", True))
    threads = int(opts.get("threads", 1) or 1)
    thread_delay_sec = float(opts.get("thread_delay_sec", 0.0) or 0.0)

    existing_action = str(opts.get("existing_action") or "skip").strip().lower()

    # Safety: don't touch very recent files (likely still being downloaded)
    min_age_sec = float(opts.get("min_age_sec", 0.0) or 0.0)

    # Translation
    translate_enabled = bool(opts.get("translate_enabled", False))
    translate_provider = str(opts.get("translate_provider") or "google")
    translate_target_lang = str(opts.get("translate_target_lang") or "zh-CN")
    translate_base_url = str(opts.get("translate_base_url") or "")
    translate_api_key = str(opts.get("translate_api_key") or "")
    translate_email = str(opts.get("translate_email") or "")

    # Network
    proxy_url = str(opts.get("proxy_url") or "").strip()

    log_lock = threading.Lock()

    def safe_log(msg: str) -> None:
        if not log_cb:
            return
        with log_lock:
            log_cb(msg)

    write_nfo_enabled = bool(opts.get("write_nfo", True))
    download_poster = bool(opts.get("download_poster", True))
    download_fanart = bool(opts.get("download_fanart", True))
    download_previews = bool(opts.get("download_previews", False))
    download_trailer = bool(opts.get("download_trailer", False))
    download_subtitle = bool(opts.get("download_subtitle", False))
    subtitle_languages = opts.get("subtitle_languages")
    preview_limit = int(opts.get("preview_limit", 8) or 8)
    nfo_fields_list = opts.get("nfo_fields")
    nfo_fields = set(nfo_fields_list) if isinstance(nfo_fields_list, list) and nfo_fields_list else None

    field_sources = opts.get("field_sources")
    if not isinstance(field_sources, dict):
        field_sources = None

    nfo_opts = NfoWriteOptions(
        write_nfo=write_nfo_enabled,
        nfo_fields=nfo_fields,
        download_poster=download_poster,
        download_fanart=download_fanart,
        download_previews=download_previews,
        download_trailer=download_trailer,
        preview_limit=preview_limit,
        proxy_url=proxy_url or None,
        log_fn=safe_log,
    )

    safe_log(f"scan: start: {directory}")
    files = scan_videos(directory)
    safe_log(f"scan: found {len(files)} files")
    if min_age_sec and min_age_sec > 0:
        now = time.time()
        eligible = []
        for p in files:
            try:
                st = p.stat()
                if now - float(st.st_mtime) >= float(min_age_sec):
                    eligible.append(p)
            except Exception:
                # If stat fails, skip to be safe
                continue
        files = eligible
        safe_log(f"scan: eligible {len(files)} files (min_age_sec={min_age_sec})")
    total = len(files)
    results: list[ScrapeItemResult] = []

    progress_lock = threading.Lock()
    completed = 0

    def bump_progress(current_file: str) -> None:
        nonlocal completed
        if not progress_cb:
            return
        with progress_lock:
            completed += 1
            progress_cb(completed, total, current_file)

    def process_one(file_path: Path, index_hint: int) -> ScrapeItemResult:
        if progress_cb:
            # Do not advance progress on "start" (especially important for threads>1).
            # Only update current_file while keeping current monotonic (completed count).
            with progress_lock:
                progress_cb(completed, total, str(file_path))

        if thread_delay_sec and thread_delay_sec > 0:
            time.sleep(thread_delay_sec)

        safe_log(f"\n=== [{index_hint}/{total}] {file_path.name} ===")

        # If writing in place and user chose to skip existing, short-circuit when NFO already exists.
        if output_dir is None and existing_action == "skip":
            try:
                if file_path.with_suffix(".nfo").exists():
                    safe_log("skip: nfo already exists (in-place)")
                    bump_progress(str(file_path))
                    media = read_media_info(file_path)
                    merged = merge_results([])
                    merged.title = merged.title or file_path.stem
                    merged.external_id = merged.external_id or file_path.stem
                    result = ScrapeItemResult(path=file_path, media=media, merged=merged, sources=[])
                    if item_cb:
                        try:
                            item_cb(result)
                        except Exception:
                            pass
                    return result
            except Exception:
                # If we can't check safely, fall through to normal processing.
                pass

        media = read_media_info(file_path)
        per_file_results = []
        safe_log("metadata: extracting from sources...")
        for c in crawlers:
            try:
                safe_log(f"try crawler: {getattr(c, 'name', 'unknown')}")
                r = c.crawl(file_path, media)
                if r:
                    safe_log(
                        f"hit crawler: {getattr(c, 'name', 'unknown')} title={r.title!r} url={r.original_url!r}"
                    )
                    try:
                        pdata = r.data or {}
                        pplot = pdata.get("plot")
                        if isinstance(pplot, str) and pplot.strip():
                            snippet = re.sub(r"\s+", " ", pplot.strip())[:160]
                            safe_log(f"  plot[{getattr(c, 'name', 'unknown')}]={snippet!r}")
                    except Exception:
                        pass
                    per_file_results.append(r)
                else:
                    safe_log(f"miss crawler: {getattr(c, 'name', 'unknown')}")
            except Exception as e:
                logger.warning(f"crawler {getattr(c, 'name', 'unknown')} failed for {file_path}: {e}")
                safe_log(f"error crawler: {getattr(c, 'name', 'unknown')} error={e}")

        safe_log("metadata: merging results...")
        merged = merge_results(per_file_results, field_sources=field_sources)
        if not per_file_results:
            merged.title = merged.title or file_path.stem
            merged.external_id = merged.external_id or file_path.stem
            merged.original_url = merged.original_url or None

        _emit_live_json(safe_log, file_path=file_path, merged=merged, per_file_results=per_file_results)

        # Debug: show merged plot before any sanitization.
        try:
            _p0 = (merged.data or {}).get("plot")
            if isinstance(_p0, str) and _p0.strip():
                safe_log(f"merged.plot(before)={_norm_ws(_p0)[:180]!r}")
        except Exception:
            pass

        # Guardrail: drop known generic site slogans accidentally scraped as plot.
        try:
            data = merged.data or {}
            plot = data.get("plot")
            if isinstance(plot, str):
                t = plot.strip()
                if any(m in t for m in ("番号搜磁链", "管理你的成人影片", "分享你的想法")):
                    data["plot"] = ""
                    merged.data = data
        except Exception:
            pass

        # Guardrail: drop JS/blocked placeholder plots (DMM often returns these when blocked).
        try:
            data = merged.data or {}
            plot = data.get("plot")
            if isinstance(plot, str) and plot.strip():
                low = re.sub(r"\s+", " ", plot.strip()).lower()
                bad = [
                    "javascriptを有効",
                    "javascriptの設定方法",
                    "無料サンプル",
                    "サンプル動画",
                    "中古品",
                    "画像をクリックして拡大",
                    "拡大サンプル画像",
                    "请启用javascript",
                    "如何设置javascript",
                    "单击图像放大",
                ]
                if any(m in low for m in bad):
                    data.setdefault("plot_original", plot)
                    data["plot"] = ""
                    merged.data = data
                    safe_log("drop plot: placeholder/js-blocked")
        except Exception:
            pass

        # Guardrail: clean DMM/FANZA-style plot strings that include metadata prefix.
        try:
            data = merged.data or {}
            plot = data.get("plot")
            if isinstance(plot, str) and plot.strip():
                t = plot.strip()
                # Trigger on common signals; be tolerant of fullwidth brackets.
                looks_like_meta = (
                    ("发布日期" in t and "时长" in t and "分钟" in t)
                    or bool(re.search(r"(?:\[|［)\s*发布日期\s*(?:\]|］)", t))
                    or bool(re.search(r"(?:\[|［)\s*时长\s*(?:\]|］)", t))
                    or ("發行日期" in t and "長度" in t and "分鐘" in t)
                    or bool(re.search(r"【\s*(?:發行日期|发行日期|发布日期)\s*】", t))
                    or bool(re.search(r"【\s*(?:長度|长度|时长)\s*】", t))
                )
                if looks_like_meta:
                    code_hint = str(merged.external_id or "").strip()
                    # Strip leading metadata blocks.
                    for _ in range(3):
                        before = t
                        t = re.sub(r"^\s*(?:\[|［)\s*发布日期\s*(?:\]|］)\s*[^，,]+\s*[，,]\s*", "", t)
                        t = re.sub(r"^\s*(?:\[|［)\s*时长\s*(?:\]|］)\s*\d+\s*分钟\s*[，,]\s*", "", t)
                        t = re.sub(r"^\s*【\s*(?:發行日期|发行日期|发布日期)\s*】\s*[^，,]+\s*[，,]\s*", "", t)
                        t = re.sub(r"^\s*【\s*(?:長度|长度|时长)\s*】\s*\d+\s*(?:分钟|分鐘)\s*[，,]\s*", "", t)
                        if t == before:
                            break
                    # Strip leading (CODE) (halfwidth/fullwidth parentheses)
                    if code_hint:
                        t = re.sub(rf"^[\(（]\s*{re.escape(code_hint)}\s*[\)）]\s*", "", t, flags=re.IGNORECASE)
                    t = re.sub(r"^[\(（][A-Za-z0-9]+-[A-Za-z0-9]+[\)）]\s*", "", t)
                    # Drop a quoted long title prefix if present.
                    t = re.sub(r"^(?:“[^”]{5,300}”|「[^」]{5,300}」|『[^』]{5,300}』)\s*", "", t)
                    t = t.lstrip(" :：-—，,")
                    t = re.sub(r"\s+", " ", t).strip()
                    if t and t != plot:
                        data.setdefault("plot_original", plot)
                        data["plot"] = t
                        merged.data = data
                        sanitized_t = re.sub(r'\s+', ' ', t)[:180]
                        safe_log(f"merged.plot(sanitized)={sanitized_t!r}")
        except Exception:
            pass

        # Debug: final plot that will be written to NFO (and then translated if enabled).
        try:
            _p1 = (merged.data or {}).get("plot")
            if isinstance(_p1, str) and _p1.strip():
                final_plot = re.sub(r'\s+', ' ', _p1.strip())[:180]
                safe_log(f"merged.plot(final)={final_plot!r}")
            else:
                safe_log("merged.plot(final)=<empty>")
        except Exception:
            pass

        # Optional translation (best effort): translate title + plot into target language.
        if translate_enabled:
            try:
                data = merged.data or {}

                # Title
                title = merged.title
                code = (merged.external_id or "").strip()
                if isinstance(title, str):
                    t = title.strip()
                    # Skip translating when title is basically just the code.
                    if t and (not code or t.upper() != code.upper()):
                        safe_log("translate: title start")
                        translated_title = translate_text(
                            t,
                            target_lang=translate_target_lang,
                            provider=translate_provider,
                            base_url=translate_base_url,
                            api_key=translate_api_key,
                            email=translate_email,
                            proxy_url=proxy_url,
                        )
                        if translated_title and translated_title.strip() and translated_title.strip() != t:
                            data.setdefault("title_original", t)
                            merged.title = translated_title.strip()
                            data["title"] = merged.title
                        safe_log("translate: title done")

                # Plot
                plot = data.get("plot")
                if isinstance(plot, str) and plot.strip():
                    safe_log("translate: plot start")
                    translated_plot = translate_text(
                        plot,
                        target_lang=translate_target_lang,
                        provider=translate_provider,
                        base_url=translate_base_url,
                        api_key=translate_api_key,
                        email=translate_email,
                        proxy_url=proxy_url,
                    )
                    if translated_plot and translated_plot.strip() and translated_plot != plot:
                        data.setdefault("plot_original", plot)
                        data["plot"] = translated_plot
                    safe_log("translate: plot done")

                merged.data = data
            except Exception as e:
                safe_log(f"translate failed: {e}")

        # Emit post-translation live metadata for real-time UI (best effort).
        try:
            data = merged.data or {}
            plot_val = data.get("plot")
            plot_text = plot_val.strip() if isinstance(plot_val, str) else ""
            plot_norm = re.sub(r"\s+", " ", plot_text).strip()
            live = {
                "phase": "post",
                "file": str(file_path),
                "file_name": str(file_path.name),
                "code": str(merged.external_id or ""),
                "title": str(merged.title or ""),
                "url": str(merged.original_url or ""),
                "release": data.get("release"),
                "runtime": data.get("runtime"),
                "studio": data.get("studio"),
                "series": data.get("series"),
                "actors": data.get("actors"),
                "tags": data.get("tags"),
                "poster_url": data.get("poster_url") or data.get("cover_url"),
                "fanart_url": data.get("fanart_url"),
                "plot_len": len(plot_text) if plot_text else 0,
                "plot_preview": plot_norm[:240] if plot_norm else "",
            }
            safe_log("live.json: " + json.dumps(live, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass

        # Determine final placement.
        final_path = file_path
        if output_dir is not None:
            safe_log("organize: moving/copying file...")
            data = merged.data or {}
            actors = data.get("actors") or []
            actor = actors[0] if actors else "Unknown"
            year = _extract_year(data.get("release"))
            code = merged.external_id or file_path.stem
            title = merged.title or file_path.stem

            rel = structure.format(
                actor=_sanitize_segment(str(actor)),
                year=_sanitize_segment(str(year)),
                code=_sanitize_segment(str(code)),
                title=_sanitize_segment(str(title)),
            )
            dest_dir = output_dir / rel
            dest_dir.mkdir(parents=True, exist_ok=True)

            base_name = _sanitize_segment(str(code)) if rename else file_path.stem
            dest_video = dest_dir / f"{base_name}{file_path.suffix}"

            # When output exists, user can choose to skip or overwrite.
            dest_nfo = dest_video.with_suffix(".nfo")
            if existing_action == "skip" and (dest_video.exists() or dest_nfo.exists()):
                safe_log("skip: output already exists")
                bump_progress(str(file_path))
                result = ScrapeItemResult(path=dest_video, media=media, merged=merged, sources=per_file_results)
                if item_cb:
                    try:
                        item_cb(result)
                    except Exception:
                        pass
                return result
            if existing_action == "overwrite" and dest_video.exists():
                try:
                    dest_video.unlink()
                except Exception:
                    pass
            if existing_action not in {"skip", "overwrite"}:
                # Backward-compatible: unknown mode -> keep old collision-avoid behavior.
                dest_video = _avoid_collision(dest_video)

            if dest_video.resolve() != file_path.resolve():
                try:
                    if copy_source:
                        shutil.copy2(str(file_path), str(dest_video))
                        final_path = dest_video
                        safe_log(f"copy: {file_path} -> {final_path}")
                    else:
                        # On some platforms shutil.move may not overwrite reliably; remove first when overwriting.
                        if existing_action == "overwrite" and dest_video.exists():
                            try:
                                dest_video.unlink()
                            except Exception:
                                pass
                        shutil.move(str(file_path), str(dest_video))
                        final_path = dest_video
                        safe_log(f"move: {file_path} -> {final_path}")
                except Exception as e:
                    safe_log(f"move failed: {e}; keep in place")

        nfo_path = write_nfo(final_path, media, merged, options=nfo_opts)
        if nfo_path is not None:
            logger.info(f"scraped: {final_path.name} -> {nfo_path.name}")
            safe_log(f"write nfo: {nfo_path.name}")
        else:
            logger.info(f"scraped: {final_path.name} (nfo disabled)")
            safe_log("nfo disabled")

        # Subtitle download
        downloaded_subs_paths = []
        if download_subtitle:
            try:
                code = (merged.external_id or file_path.stem).strip()
                if code:
                    safe_log(f"subtitle: searching for {code}")
                    sub_crawler = SubtitleCatCrawler(proxy_url=proxy_url, log_fn=safe_log)
                    downloaded_subs = sub_crawler.search_and_download(
                        keyword=code,
                        save_path_base=final_path.with_suffix(""),
                        languages=subtitle_languages
                    )
                    if downloaded_subs:
                        safe_log(f"subtitle: downloaded {len(downloaded_subs)} files")
                        downloaded_subs_paths = downloaded_subs
                    else:
                        safe_log("subtitle: no subtitles found")
            except Exception as e:
                safe_log(f"subtitle: failed {e}")
        
        # Emit live json again with subtitle info
        _emit_live_json(safe_log, file_path=file_path, merged=merged, per_file_results=per_file_results, subtitles=downloaded_subs_paths)

        # Always check for local preview files so API/UI can prefer them over remote URLs.
        # This works whether previews were downloaded this run or existed from a previous run.
        if nfo_path is not None:
            try:
                preview_files = sorted(
                    [p.name for p in final_path.parent.glob(f"{final_path.stem}-preview-*.*") if p.is_file()]
                )
                if preview_files:
                    data = merged.data or {}
                    data["preview_files"] = preview_files
                    merged.data = data
            except Exception as e:
                safe_log(f"warn: failed to enumerate downloaded preview files: {e}")

            # Check for local trailer file
            try:
                trailer_patterns = [
                    final_path.with_name(f"{final_path.stem}-trailer.mp4"),
                    final_path.with_name(f"{final_path.stem}-trailer.webm"),
                    final_path.with_name(f"{final_path.stem}-trailer.mkv"),
                ]
                for tp in trailer_patterns:
                    if tp.exists() and tp.is_file():
                        data = merged.data or {}
                        data["trailer_file"] = tp.name
                        merged.data = data
                        break
            except Exception as e:
                safe_log(f"warn: failed to check for trailer file: {e}")

        result = ScrapeItemResult(
            path=final_path, 
            media=media, 
            merged=merged, 
            sources=per_file_results,
            subtitles=downloaded_subs_paths
        )
        # Record the completed item first so the UI history doesn't briefly lose the just-finished row
        # when the runner switches to the next file.
        if item_cb:
            try:
                item_cb(result)
            except Exception:
                pass
        # Keep progress current_file stable: prefer the input filename to match log markers.
        bump_progress(str(file_path))
        return result

    if threads <= 1:
        for idx, file_path in enumerate(files, 1):
            results.append(process_one(file_path, idx))
        return results

    max_workers = max(1, min(int(threads), 32))
    safe_log(f"parallel: threads={max_workers}")
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {}
        for idx, file_path in enumerate(files, 1):
            futures[ex.submit(process_one, file_path, idx)] = file_path

        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                fp = futures.get(fut)
                safe_log(f"file failed: {fp}: {e}")

    # Keep stable ordering for UI
    results.sort(key=lambda r: str(r.path))

    return results
