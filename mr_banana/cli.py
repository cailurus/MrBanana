"""
Mr. Banana CLI - jable.tv 视频下载命令行工具
"""
import argparse
import os
import sys

from mr_banana.downloader import MovieDownloader
from mr_banana.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Mr. Banana: jable.tv 视频下载工具"
    )

    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="jable.tv 视频页面 URL"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="downloads",
        help="下载输出目录 (默认: downloads)"
    )
    parser.add_argument(
        "--format",
        type=str,
        default="{id}",
        help="文件名格式，支持 {id} 和 {title} (默认: {id})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    logger.info("Starting Mr. Banana...")
    logger.info(f"Target URL: {args.url}")
    logger.info(f"Output directory: {args.output_dir}")

    if not os.path.exists(args.output_dir):
        try:
            os.makedirs(args.output_dir)
            logger.info(f"Created directory: {args.output_dir}")
        except OSError as e:
            logger.error(f"Failed to create directory {args.output_dir}: {e}")
            sys.exit(1)

    downloader = MovieDownloader()
    try:
        downloader.download(
            url=args.url,
            output_dir=args.output_dir,
            filename_format=args.format
        )
    except KeyboardInterrupt:
        logger.info("\nDownload interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
