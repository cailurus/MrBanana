"""
Shared test fixtures for Mr. Banana tests.

The key benefit of DI: tests use app.dependency_overrides to inject mocks,
never instantiating real managers, touching real databases, or making HTTP requests.
"""
import os
import tempfile

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import (
    get_download_manager,
    get_scrape_manager,
    get_subscription_manager,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def mock_download_manager():
    """Create a mock DownloadManager for testing."""
    mock = MagicMock()
    mock.active_tasks = {}
    mock.active_connections = []
    mock.history_manager = MagicMock()
    mock.history_manager.get_history.return_value = []
    mock.start_download.return_value = {"status": "success", "task_id": 1}
    mock.resume_download.return_value = {"status": "success", "task_id": 1}
    mock.pause_task.return_value = {"status": "success", "task_id": 1}
    mock.delete_task.return_value = {"status": "success", "task_id": 1}
    mock.read_task_log.return_value = {"exists": False, "text": "", "next_offset": 0}
    mock.cleanup_logs.return_value = {"status": "success", "deleted": 0, "errors": 0}
    mock.clear_history.return_value = {"status": "success", "deleted_db_rows": 0, "deleted_logs": 0, "errors": 0}
    mock.get_active_tasks_snapshot.return_value = {}
    return mock


@pytest.fixture
def mock_scrape_manager():
    """Create a mock ScrapeManager for testing."""
    mock = MagicMock()
    mock.get_config.return_value = {"scrape_dir": "/tmp/test"}
    mock.list_jobs.return_value = []
    mock.list_items.return_value = []
    mock.list_history_items.return_value = []
    mock.start_job.return_value = {"status": "success", "job_id": 1}
    mock.pending_count.return_value = {"status": "success", "count": 0, "directory": "/tmp"}
    mock.cleanup_logs.return_value = {"status": "success", "deleted": 0, "errors": 0}
    mock.clear_history.return_value = {"status": "success", "deleted_files": 0, "errors": 0}
    return mock


@pytest.fixture
def mock_subscription_manager():
    """Create a mock SubscriptionManager for testing."""
    mock = MagicMock()
    mock.get_subscriptions.return_value = []
    mock.get_config.return_value = {
        "check_interval_days": 1,
        "telegram_enabled": 0,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
    }
    mock.add_subscription.return_value = 1
    mock.remove_subscription.return_value = True
    mock.mark_as_read.return_value = True
    mock.clear_all.return_value = 0
    return mock


@pytest.fixture
def di_client(mock_download_manager, mock_scrape_manager, mock_subscription_manager):
    """Create a test client with all dependencies mocked via DI overrides."""
    app = create_app()
    app.dependency_overrides[get_download_manager] = lambda: mock_download_manager
    app.dependency_overrides[get_scrape_manager] = lambda: mock_scrape_manager
    app.dependency_overrides[get_subscription_manager] = lambda: mock_subscription_manager

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
