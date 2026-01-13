"""
HLS 视频下载模块 - 支持并发下载 m3u8 视频流
"""
import os
import shutil
import time
import m3u8
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from mr_banana.utils.logger import logger
from mr_banana.utils.network import NetworkHandler


class DownloadCancelled(Exception):
    pass


class HLSDownloader:
    """HLS (m3u8) 视频下载器"""

    def __init__(self, network_handler: NetworkHandler, max_workers: int = 16):
        self.network = network_handler
        self.max_workers = max_workers

    def download(
        self,
        m3u8_url: str,
        output_path: str,
        headers: dict[str, str] | None = None,
        progress_callback=None,
        cancel_event=None,
        preferred_resolution: str | None = None,
    ) -> bool:
        """
        下载 HLS 视频
        
        Args:
            m3u8_url: m3u8 播放列表 URL
            output_path: 输出文件路径
            progress_callback: 进度回调 (current, total, speed_str, total_bytes)
        
        Returns:
            bool: 下载是否成功
        """
        if cancel_event and cancel_event.is_set():
            raise DownloadCancelled()

        def _parse_target_height(pref: str | None) -> int | None:
            if not pref:
                return None
            s = str(pref).strip().lower()
            if s in {"best", "auto"}:
                return None
            if s.endswith("p") and s[:-1].isdigit():
                return int(s[:-1])
            if s.isdigit():
                return int(s)
            return None

        def _select_variant_url(master: m3u8.M3U8, base_uri: str) -> str | None:
            if not getattr(master, "playlists", None):
                return None

            target_h = _parse_target_height(preferred_resolution)

            def info(pl):
                si = getattr(pl, "stream_info", None)
                bw = int(getattr(si, "bandwidth", 0) or 0)
                res = getattr(si, "resolution", None)
                h = None
                try:
                    if res and isinstance(res, (tuple, list)) and len(res) == 2:
                        h = int(res[1])
                except Exception:
                    h = None
                return bw, h

            candidates = []
            for pl in master.playlists:
                uri = getattr(pl, "uri", None)
                if not uri:
                    continue
                bw, h = info(pl)
                abs_uri = uri if uri.startswith(("http://", "https://")) else urljoin(base_uri, uri)
                candidates.append((abs_uri, bw, h))

            if not candidates:
                return None

            # Best quality
            if target_h is None:
                candidates.sort(key=lambda x: (x[2] or 0, x[1]), reverse=True)
                return candidates[0][0]

            under = [c for c in candidates if c[2] is not None and c[2] <= target_h]
            if under:
                under.sort(key=lambda x: (x[2] or 0, x[1]), reverse=True)
                return under[0][0]

            # If no variant under target, pick the smallest above target (or overall lowest) to avoid overshooting too much.
            above = [c for c in candidates if c[2] is not None]
            if above:
                above.sort(key=lambda x: (abs((x[2] or 0) - target_h), -(x[1] or 0)))
                return above[0][0]

            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # 获取 m3u8 内容（若是 master playlist，则按分辨率选择 variant）
        playlist = None
        content = None
        for _ in range(2):
            content = self.network.get(m3u8_url, headers=headers)
            if not content:
                logger.error("Failed to fetch m3u8 playlist")
                return False

            if cancel_event and cancel_event.is_set():
                raise DownloadCancelled()

            playlist = m3u8.loads(content)
            if playlist.segments:
                break

            # master playlist
            base_uri = m3u8_url.rsplit('/', 1)[0] + '/'
            variant_url = _select_variant_url(playlist, base_uri)
            if variant_url:
                m3u8_url = variant_url
                continue
            break

        if not playlist or not playlist.segments:
            logger.error("No segments found in playlist")
            return False

        logger.info(f"Found {len(playlist.segments)} segments")

        # 准备临时目录
        temp_dir = output_path + "_temp"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        try:
            base_uri = m3u8_url.rsplit('/', 1)[0] + '/'

            # 下载加密密钥（如果存在）
            for key in playlist.keys:
                if key and key.uri:
                    if not key.uri.startswith(('http://', 'https://')):
                        key.uri = urljoin(base_uri, key.uri)

                    key_content = self.network.download_file(key.uri, headers=headers)
                    if key_content:
                        key_filename = "key.key"
                        with open(os.path.join(temp_dir, key_filename), "wb") as f:
                            f.write(key_content)
                        key.uri = key_filename

            # 并发下载分段
            segments_to_download = []
            for i, segment in enumerate(playlist.segments):
                if not segment.uri.startswith(('http://', 'https://')):
                    segment.uri = urljoin(base_uri, segment.uri)

                filename = f"seg_{i:05d}.ts"
                segments_to_download.append((segment.uri, os.path.join(temp_dir, filename)))
                segment.uri = filename

            logger.info(f"Downloading {len(segments_to_download)} segments with {self.max_workers} workers...")

            total_bytes = 0
            start_time = time.time()
            failed_segments = []

            executor = ThreadPoolExecutor(max_workers=self.max_workers)
            cancelled = False
            try:
                completed_count = 0
                total_count = len(segments_to_download)

                pending = set()
                future_to_item = {}
                it = iter(segments_to_download)

                def submit_next() -> bool:
                    try:
                        u, p = next(it)
                    except StopIteration:
                        return False
                    fut = executor.submit(self._download_segment, u, p, cancel_event, headers)
                    pending.add(fut)
                    future_to_item[fut] = (u, p)
                    return True

                # 预热提交
                for _ in range(self.max_workers):
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        raise DownloadCancelled()
                    if not submit_next():
                        break

                while pending:
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        for fut in pending:
                            fut.cancel()
                        raise DownloadCancelled()

                    # 取一个完成的 future
                    try:
                        future = next(as_completed(pending, timeout=0.2))
                    except TimeoutError:
                        continue

                    pending.remove(future)
                    url, path = future_to_item.pop(future, (None, None))

                    try:
                        size = future.result()
                        if size > 0:
                            total_bytes += size
                            completed_count += 1
                        else:
                            failed_segments.append((url, path))
                    except DownloadCancelled:
                        cancelled = True
                        raise
                    except Exception as e:
                        logger.error(f"Segment download error: {e}")
                        failed_segments.append((url, path))

                    # 补充提交
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        for fut in pending:
                            fut.cancel()
                        raise DownloadCancelled()
                    submit_next()

                    # 更新进度
                    elapsed = time.time() - start_time
                    speed_str = "0 B/s"
                    if elapsed > 0:
                        speed = total_bytes / elapsed
                        speed_str = f"{self._format_bytes(speed)}/s"

                    if progress_callback:
                        progress_callback(completed_count, total_count, speed_str, total_bytes)
            finally:
                executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

            # 重试失败的分段
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelled()

            # 重试失败的分段
            if failed_segments:
                logger.warning(f"{len(failed_segments)} segments failed; retrying...")
                # 保守起见：按本地文件缺失/为空来重试（覆盖未来可能的中断情况）
                missing = [
                    (url, path)
                    for url, path in segments_to_download
                    if (not os.path.exists(path)) or os.path.getsize(path) == 0
                ]

                for url, path in missing:
                    if cancel_event and cancel_event.is_set():
                        raise DownloadCancelled()
                    for _ in range(3):
                        if self._download_segment(url, path, cancel_event, headers) > 0:
                            break
                        time.sleep(1)

            # 保存本地 m3u8
            local_m3u8_path = os.path.join(temp_dir, "local.m3u8")
            with open(local_m3u8_path, "w", encoding="utf-8") as f:
                f.write(playlist.dumps())

            # 使用 FFmpeg 合并
            logger.info("Merging segments...")
            if progress_callback:
                progress_callback(total_count, total_count, "Merging...", total_bytes)

            if cancel_event and cancel_event.is_set():
                raise DownloadCancelled()

            self._merge_with_ffmpeg(local_m3u8_path, output_path)

            return True

        except DownloadCancelled:
            raise
        except Exception as e:
            logger.error(f"HLS download failed: {e}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _download_segment(self, url: str, path: str, cancel_event=None, headers: dict[str, str] | None = None) -> int:
        """下载单个分段"""
        if cancel_event and cancel_event.is_set():
            raise DownloadCancelled()
        content = self.network.download_file(url, headers=headers)
        if content:
            with open(path, "wb") as f:
                f.write(content)
            return len(content)
        return 0

    def _merge_with_ffmpeg(self, m3u8_path: str, output_path: str):
        """使用 FFmpeg 合并分段"""
        cmd = [
            "ffmpeg",
            "-allowed_extensions", "ALL",
            "-i", m3u8_path,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_path,
            "-y",
            "-v", "error"
        ]
        subprocess.run(cmd, check=True)

    def _format_bytes(self, size: float) -> str:
        """格式化字节数"""
        power = 2**10
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}B"