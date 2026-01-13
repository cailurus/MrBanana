"""
API Constants and Configuration
"""
import os

# API Version
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Pagination defaults
DEFAULT_HISTORY_LIMIT = 50
DEFAULT_JOBS_LIMIT = 20
DEFAULT_ITEMS_LIMIT = 500
DEFAULT_LIBRARY_LIMIT = 200
MAX_LIBRARY_LIMIT = 500

# Download settings
MIN_DOWNLOAD_WORKERS = 1
MAX_DOWNLOAD_WORKERS = 128
DEFAULT_DOWNLOAD_WORKERS = 16

# Scrape settings
MIN_SCRAPE_INTERVAL_SEC = 30
DEFAULT_SCRAPE_INTERVAL_SEC = 3600
MIN_POLL_SEC = 2.0
MAX_POLL_SEC = 120.0
DEFAULT_POLL_SEC = 10.0
MIN_QUIET_SEC = 5.0
MAX_QUIET_SEC = 600.0
DEFAULT_QUIET_SEC = 30.0
DEFAULT_MIN_AGE_SEC = 300.0

# File limits
MAX_LOG_READ_BYTES = 65536
MAX_JOBS_PERSIST = 200

# Valid resolutions for download
VALID_RESOLUTIONS = {"best", "1080p", "720p", "480p", "360p"}

# Valid image extensions
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Valid video extensions
VALID_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
