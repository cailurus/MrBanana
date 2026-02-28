"""
Tests for crawler code extraction and URL parsing.
"""
import pytest
from pathlib import Path

from mr_banana.scraper.crawlers.base import extract_jav_code
from mr_banana.downloader import normalize_jable_input


class TestExtractJavCode:
    """Test JAV code extraction from filenames."""

    def test_standard_code(self):
        assert extract_jav_code(Path("ADN-529.mp4")) == "ADN-529"

    def test_uppercase(self):
        assert extract_jav_code(Path("SSIS-001.mp4")) == "SSIS-001"

    def test_lowercase(self):
        assert extract_jav_code(Path("ssis-001.mp4")) == "SSIS-001"

    def test_with_suffix(self):
        assert extract_jav_code(Path("ADN-529-C.mp4")) == "ADN-529"

    def test_with_ch_suffix(self):
        assert extract_jav_code(Path("ADN-748ch.mp4")) == "ADN-748"

    def test_with_prefix(self):
        assert extract_jav_code(Path("4k2.me@adn-757ch.mp4")) == "ADN-757"

    def test_no_hyphen(self):
        assert extract_jav_code(Path("adn529.mp4")) == "ADN-529"

    def test_no_code(self):
        assert extract_jav_code(Path("random_video.mp4")) is None

    def test_empty_stem(self):
        assert extract_jav_code(Path(".mp4")) is None

    def test_long_code(self):
        assert extract_jav_code(Path("WAAA-585.mp4")) == "WAAA-585"


class TestNormalizeJableInput:
    """Test URL normalization for Jable.tv."""

    def test_full_url(self):
        url, code = normalize_jable_input("https://jable.tv/videos/ssis-001/")
        assert "jable.tv" in url
        assert code is None

    def test_code_to_url(self):
        url, code = normalize_jable_input("SSIS-001")
        assert url == "https://jable.tv/videos/ssis-001/"
        assert code == "ssis-001"

    def test_code_with_spaces(self):
        url, code = normalize_jable_input("  SSIS-001  ")
        assert url == "https://jable.tv/videos/ssis-001/"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_jable_input("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            normalize_jable_input(None)

    def test_non_jable_url_raises(self):
        with pytest.raises(ValueError):
            normalize_jable_input("https://example.com/video")

    def test_url_without_scheme(self):
        url, code = normalize_jable_input("jable.tv/videos/test-123/")
        assert url.startswith("https://")
        assert "jable.tv" in url

    def test_http_url(self):
        url, code = normalize_jable_input("http://jable.tv/videos/test-123/")
        assert url == "http://jable.tv/videos/test-123/"
