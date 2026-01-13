"""
Tests for HistoryManager
"""
import os
import sqlite3
import tempfile
import threading
import pytest

from mr_banana.utils.history import HistoryManager


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def history_manager(temp_db):
    """Create a HistoryManager instance with a temporary database."""
    return HistoryManager(db_path=temp_db)


class TestHistoryManager:
    """Test HistoryManager functionality."""

    def test_add_task(self, history_manager):
        """Test adding a task."""
        task_id = history_manager.add_task("https://example.com/video", status="Preparing")
        assert task_id > 0

    def test_get_task(self, history_manager):
        """Test retrieving a task by ID."""
        task_id = history_manager.add_task("https://example.com/video", status="Preparing")
        task = history_manager.get_task(task_id)
        assert task is not None
        assert task["url"] == "https://example.com/video"
        assert task["status"] == "Preparing"

    def test_update_task_status(self, history_manager):
        """Test updating a task's status."""
        task_id = history_manager.add_task("https://example.com/video", status="Preparing")
        history_manager.update_task(task_id, status="Completed", output_path="/path/to/video.mp4")
        
        task = history_manager.get_task(task_id)
        assert task["status"] == "Completed"
        assert task["output_path"] == "/path/to/video.mp4"
        assert task["completed_at"] is not None

    def test_delete_task(self, history_manager):
        """Test deleting a task."""
        task_id = history_manager.add_task("https://example.com/video", status="Preparing")
        history_manager.delete_task(task_id)
        
        task = history_manager.get_task(task_id)
        assert task is None

    def test_get_history(self, history_manager):
        """Test retrieving download history."""
        # Add multiple tasks
        for i in range(5):
            history_manager.add_task(f"https://example.com/video{i}", status="Completed")
        
        history = history_manager.get_history(limit=10)
        assert len(history) == 5

    def test_get_history_limit(self, history_manager):
        """Test that history respects limit parameter."""
        for i in range(10):
            history_manager.add_task(f"https://example.com/video{i}", status="Completed")
        
        history = history_manager.get_history(limit=3)
        assert len(history) == 3

    def test_is_url_completed(self, history_manager):
        """Test checking if URL is completed."""
        url = "https://example.com/video"
        task_id = history_manager.add_task(url, status="Preparing")
        
        assert not history_manager.is_url_completed(url)
        
        history_manager.update_task(task_id, status="Completed")
        assert history_manager.is_url_completed(url)

    def test_mark_incomplete_as_paused(self, history_manager):
        """Test marking incomplete tasks as paused."""
        # Add tasks with different statuses
        history_manager.add_task("https://example.com/1", status="Preparing")
        history_manager.add_task("https://example.com/2", status="Downloading")
        task_id3 = history_manager.add_task("https://example.com/3", status="Completed")
        history_manager.update_task(task_id3, status="Completed")
        
        count = history_manager.mark_incomplete_as_paused()
        assert count == 2  # Only Preparing and Downloading should be marked
        
        history = history_manager.get_history(limit=10)
        statuses = [h["status"] for h in history]
        assert statuses.count("Paused") == 2
        assert statuses.count("Completed") == 1

    def test_clear_all(self, history_manager):
        """Test clearing all history."""
        for i in range(5):
            history_manager.add_task(f"https://example.com/video{i}", status="Completed")
        
        deleted = history_manager.clear_all()
        assert deleted == 5
        
        history = history_manager.get_history(limit=10)
        assert len(history) == 0

    def test_scrape_after_download_fields(self, history_manager):
        """Test scrape-after-download related fields."""
        task_id = history_manager.add_task(
            "https://example.com/video",
            status="Preparing",
            scrape_after_download=True
        )
        
        task = history_manager.get_task(task_id)
        assert task["scrape_after_download"] == 1
        assert task["scrape_status"] == "Pending"
        
        history_manager.update_scrape(task_id, scrape_job_id=42, scrape_status="Running")
        task = history_manager.get_task(task_id)
        assert task["scrape_job_id"] == 42
        assert task["scrape_status"] == "Running"


class TestHistoryManagerConcurrency:
    """Test HistoryManager thread safety."""

    def test_concurrent_writes(self, history_manager):
        """Test that concurrent writes don't cause database lock errors."""
        errors = []
        
        def add_tasks(start_idx):
            try:
                for i in range(10):
                    history_manager.add_task(
                        f"https://example.com/video{start_idx}_{i}",
                        status="Completed"
                    )
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=add_tasks, args=(i * 10,))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        
        history = history_manager.get_history(limit=100)
        assert len(history) == 50

    def test_concurrent_read_write(self, history_manager):
        """Test that concurrent reads and writes work correctly."""
        errors = []
        
        def writer():
            try:
                for i in range(20):
                    history_manager.add_task(f"https://example.com/video{i}", status="Completed")
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for _ in range(20):
                    history_manager.get_history(limit=10)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrent read/write errors: {errors}"
