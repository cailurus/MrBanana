"""
Tests for subscription check logic with mocked crawler.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from api.subscription_checker import check_one_subscription


class TestCheckOneSubscription:
    """Test single subscription check with mocked JavDB crawler."""

    def _make_sub(self, code="TEST-001", magnets=None):
        return {
            "id": 1,
            "code": code,
            "magnet_links": magnets or [],
            "has_update": False,
            "update_detail": None,
            "javdb_url": None,
        }

    def test_no_update_same_magnets(self):
        """When crawler returns same magnets, no update flagged."""
        old_magnets = [{"url": "magnet:?xt=urn:btih:abc123", "name": "TEST-001"}]
        sub = self._make_sub(magnets=old_magnets)

        mock_crawler = MagicMock()
        mock_result = MagicMock()
        mock_result.data = {"magnet_links": old_magnets}
        mock_result.original_url = "https://javdb.com/v/test"
        mock_crawler.search_by_code.return_value = mock_result

        mock_manager = MagicMock()

        result = check_one_subscription(sub, mock_crawler, mock_manager)
        assert result["has_update"] is False
        assert result["new_count"] == 0

    def test_update_new_magnets(self):
        """When crawler returns new magnets, update is flagged."""
        old_magnets = [{"url": "magnet:?xt=urn:btih:abc123", "name": "TEST-001"}]
        new_magnets = old_magnets + [{"url": "magnet:?xt=urn:btih:def456", "name": "TEST-001 HD"}]
        sub = self._make_sub(magnets=old_magnets)

        mock_crawler = MagicMock()
        mock_result = MagicMock()
        mock_result.data = {"magnet_links": new_magnets}
        mock_result.original_url = "https://javdb.com/v/test"
        mock_crawler.search_by_code.return_value = mock_result

        mock_manager = MagicMock()

        result = check_one_subscription(sub, mock_crawler, mock_manager)
        assert result["has_update"] is True
        assert result["new_count"] == 1

    def test_crawler_returns_none(self):
        """When crawler finds nothing, subscription is just updated with last_checked_at."""
        sub = self._make_sub()

        mock_crawler = MagicMock()
        mock_crawler.search_by_code.return_value = None

        mock_manager = MagicMock()

        result = check_one_subscription(sub, mock_crawler, mock_manager)
        assert result["has_update"] is False
        mock_manager.update_subscription.assert_called_once()

    def test_crawler_returns_empty_data(self):
        """When crawler returns result with no data."""
        sub = self._make_sub()

        mock_crawler = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_crawler.search_by_code.return_value = mock_result

        mock_manager = MagicMock()

        result = check_one_subscription(sub, mock_crawler, mock_manager)
        assert result["has_update"] is False
