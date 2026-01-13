"""
Tests for Mr. Banana API
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestHealthCheck:
    """Test API health and basic connectivity."""

    def test_root_endpoint(self, client):
        """Test that the root endpoint returns successfully."""
        response = client.get("/")
        assert response.status_code in (200, 404)  # 404 if static files not built

    def test_api_not_found(self, client):
        """Test that unknown API endpoints return 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404


class TestDownloadAPI:
    """Test download-related API endpoints."""

    def test_get_download_config(self, client):
        """Test fetching download configuration."""
        response = client.get("/api/download/config")
        assert response.status_code == 200
        data = response.json()
        assert "output_dir" in data
        assert "max_download_workers" in data

    def test_get_history(self, client):
        """Test fetching download history."""
        response = client.get("/api/history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_download_invalid_url(self, client):
        """Test download with invalid URL."""
        response = client.post("/api/download", json={
            "url": "",
            "output_dir": "downloads"
        })
        assert response.status_code == 422  # Validation error

    def test_download_url_too_long(self, client):
        """Test download with URL exceeding max length."""
        long_url = "https://example.com/" + "a" * 3000
        response = client.post("/api/download", json={
            "url": long_url,
            "output_dir": "downloads"
        })
        assert response.status_code == 422  # Validation error


class TestScrapeAPI:
    """Test scrape-related API endpoints."""

    def test_get_scrape_config(self, client):
        """Test fetching scrape configuration."""
        response = client.get("/api/scrape/config")
        assert response.status_code == 200
        data = response.json()
        assert "scrape_dir" in data

    def test_list_scrape_jobs(self, client):
        """Test listing scrape jobs."""
        response = client.get("/api/scrape/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_scrape_start_invalid_directory(self, client):
        """Test starting scrape with invalid directory."""
        response = client.post("/api/scrape/start", json={
            "directory": "/nonexistent/path/that/does/not/exist"
        })
        assert response.status_code in (400, 404)


class TestPlayerAPI:
    """Test player-related API endpoints."""

    def test_get_player_config(self, client):
        """Test fetching player configuration."""
        response = client.get("/api/player/config")
        assert response.status_code == 200
        data = response.json()
        assert "player_root_dir" in data


class TestSecurityValidation:
    """Test security-related validations."""

    def test_path_traversal_download(self, client):
        """Test that path traversal is blocked in download config."""
        response = client.post("/api/download/config", json={
            "output_dir": "../../../etc/passwd"
        })
        assert response.status_code == 400

    def test_path_traversal_scrape(self, client):
        """Test that path traversal is blocked in scrape start."""
        response = client.post("/api/scrape/start", json={
            "directory": "../../../etc"
        })
        assert response.status_code == 400
