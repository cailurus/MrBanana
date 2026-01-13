"""
日志模块
"""
import logging
import os
import sys
import threading


_task_ctx = threading.local()

# 日志文件存放在项目根目录的 logs/ 目录下
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
DEFAULT_LOG_FILE = os.path.join(LOGS_DIR, "mr_banana.log")

# Log level mapping from string to logging constant
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def get_log_level_from_env() -> int:
    """Get log level from environment variable LOG_LEVEL or MR_BANANA_LOG_LEVEL."""
    level_str = os.environ.get("MR_BANANA_LOG_LEVEL") or os.environ.get("LOG_LEVEL") or "INFO"
    return LOG_LEVEL_MAP.get(level_str.upper(), logging.INFO)


def set_task_id(task_id: int | str | None) -> None:
    """Set current thread's task id for log routing."""
    if task_id is None:
        clear_task_id()
        return
    _task_ctx.task_id = str(task_id)


def clear_task_id() -> None:
    """Clear current thread's task id for log routing."""
    if hasattr(_task_ctx, "task_id"):
        delattr(_task_ctx, "task_id")


class InjectTaskIdFilter(logging.Filter):
    """Injects task_id into LogRecord (thread-local), defaulting to '-'"""

    def filter(self, record: logging.LogRecord) -> bool:
        task_id = getattr(_task_ctx, "task_id", "-")
        record.task_id = task_id
        return True


class MatchTaskIdFilter(logging.Filter):
    """Only allow records that match a specific task id."""

    def __init__(self, task_id: int | str):
        super().__init__()
        self._task_id = str(task_id)

    def filter(self, record: logging.LogRecord) -> bool:
        return str(getattr(record, "task_id", "-")) == self._task_id


def setup_logger(name="mr_banana", level=None, log_file=None):
    """配置并返回日志记录器
    
    Args:
        name: Logger name
        level: Log level (if None, read from environment variable)
        log_file: Log file path (if None, use default in logs/ directory)
    """
    if level is None:
        level = get_log_level_from_env()
    
    if log_file is None:
        log_file = DEFAULT_LOG_FILE
    
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Ensure task_id is always present on records (used by per-task log handlers)
    if not any(isinstance(f, InjectTaskIdFilter) for f in logger.filters):
        logger.addFilter(InjectTaskIdFilter())

    # 防止重复添加处理器
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
