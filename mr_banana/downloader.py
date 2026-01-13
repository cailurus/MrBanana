"""
Mr. Banana Video Downloader - 专门用于 jable.tv 视频下载
"""
import re
import os
from typing import Optional, Callable

from mr_banana.extractors.jable import JableExtractor
from mr_banana.utils.hls import HLSDownloader
from mr_banana.utils.logger import logger
from mr_banana.utils.network import NetworkHandler


_JABLE_HOST_RE = re.compile(r"(^|\.)jable\.tv$", re.IGNORECASE)


def normalize_jable_input(url_or_code: str) -> tuple[str, str | None]:
    """Normalize a user input into a canonical jable.tv video page URL.

    Returns:
        (url, code) where code is set only when input looked like a number/code.
    """
    raw = "" if url_or_code is None else str(url_or_code)
    s = raw.strip()
    if not s:
        raise ValueError("Please enter a jable.tv URL or a code")

    lowered = s.lower()
    if "jable.tv" in lowered:
        # Ensure scheme for robustness.
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return s, None
        return f"https://{s.lstrip('/')}", None

    # If it's already a URL but not jable, treat as unsupported.
    if lowered.startswith("http://") or lowered.startswith("https://"):
        raise ValueError(f"Only jable.tv URLs or codes are supported: {s}")

    # Treat as a code (番号). jable uses lowercase path segments.
    code = re.sub(r"\s+", "", s).strip().lower()
    if not code:
        raise ValueError("Please enter a jable.tv URL or a code")
    return f"https://jable.tv/videos/{code}/", code


class MovieDownloader:
    """Jable.tv 视频下载器"""

    def __init__(self, max_workers: int = 16, proxies: Optional[dict] = None):
        self.network_handler = NetworkHandler(proxies=proxies)
        self.extractor = JableExtractor(self.network_handler)
        self.hls_downloader = HLSDownloader(self.network_handler, max_workers=max_workers)

    def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[Callable] = None,
        filename_format: str = "{id}",
        cancel_event=None,
        preferred_resolution: str | None = None,
    ) -> str:
        """
        下载视频
        
        Args:
            url: jable.tv 视频页面 URL
            output_dir: 输出目录
            progress_callback: 进度回调函数 (current, total, speed_str, total_bytes)
            filename_format: 文件名格式，支持 {id} 和 {title} 占位符
        """
        normalized_url, code = normalize_jable_input(url)

        if not self.extractor.can_handle(normalized_url):
            logger.error(f"Unsupported URL: {normalized_url}")
            raise ValueError(f"Only jable.tv URLs or codes are supported: {url}")

        try:
            info = self.extractor.extract(normalized_url)
        except Exception as e:
            if code:
                raise ValueError(f"Code not found: {code}") from e
            raise
        if not info:
            logger.error("Failed to extract video info")
            if code:
                raise ValueError(f"Code not found: {code}")
            raise ValueError("Failed to extract video info")

        if cancel_event and getattr(cancel_event, "is_set", None) and cancel_event.is_set():
            # 协作式取消：尽早退出
            from mr_banana.utils.hls import DownloadCancelled
            raise DownloadCancelled()

        return self._process_download(
            info,
            output_dir,
            progress_callback,
            filename_format,
            cancel_event,
            preferred_resolution,
        )

    def _process_download(
        self,
        info: dict,
        output_dir: str,
        progress_callback: Optional[Callable] = None,
        filename_format: str = "{id}",
        cancel_event=None,
        preferred_resolution: str | None = None,
    ) -> str:
        """处理下载任务"""
        title = info.get("title", "video")
        video_url = info.get("video_url")
        movie_id = info.get("id")

        # 清理标题中的非法字符
        safe_title = "".join(
            c for c in title if c.isalpha() or c.isdigit() or c in " .-_"
        ).strip()

        # 格式化文件名
        try:
            filename_base = filename_format.format(id=movie_id, title=safe_title)
        except KeyError:
            filename_base = movie_id

        output_filename = f"{filename_base}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        if os.path.exists(output_path):
            logger.warning(f"File already exists: {output_path}")
            raise FileExistsError(f"File already exists: {output_path}")

        logger.info(f"Downloading: {title}")
        logger.info(f"Video URL: {video_url}")
        logger.info(f"Output path: {output_path}")

        if cancel_event and getattr(cancel_event, "is_set", None) and cancel_event.is_set():
            from mr_banana.utils.hls import DownloadCancelled
            raise DownloadCancelled()

        if self.hls_downloader.download(
            video_url,
            output_path,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            preferred_resolution=preferred_resolution,
        ):
            logger.info("Download completed!")
            return output_path
        else:
            logger.error("Download failed")
            raise RuntimeError("Download failed")