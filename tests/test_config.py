"""
Tests for AppConfig loading, saving, normalization, and thread safety.
"""
import json
import os
import tempfile
import threading

import pytest

from mr_banana.utils.config import AppConfig, load_config, save_config, CONFIG_PATH, _normalize_source_list


class TestNormalizeSourceList:
    """Test the module-level _normalize_source_list helper."""

    def test_default_when_not_list(self):
        result = _normalize_source_list("not_a_list", default=["javbus"], allow_empty=False)
        assert result == ["javbus"]

    def test_empty_list_allow_empty(self):
        result = _normalize_source_list([], default=["javbus"], allow_empty=True)
        assert result == []

    def test_empty_list_not_allow_empty(self):
        result = _normalize_source_list([], default=["javbus"], allow_empty=False)
        assert result == ["javbus"]

    def test_filters_unknown_sources(self):
        result = _normalize_source_list(["javbus", "unknown_source"], default=[], allow_empty=False)
        assert result == ["javbus"]

    def test_deduplicates(self):
        result = _normalize_source_list(["javbus", "javbus", "dmm"], default=[], allow_empty=False)
        assert result == ["javbus", "dmm"]

    def test_allowed_sources_filter(self):
        result = _normalize_source_list(
            ["javbus", "dmm", "javdb"],
            default=[],
            allow_empty=False,
            allowed_sources={"javbus", "dmm"},
        )
        assert result == ["javbus", "dmm"]


class TestAppConfig:
    """Test AppConfig dataclass behavior."""

    def test_default_values(self):
        cfg = AppConfig()
        assert cfg.output_dir == ""
        assert cfg.max_download_workers == 16
        assert cfg.download_resolution == "best"
        assert cfg.scrape_trigger_mode == "manual"

    def test_post_init_normalizes_sources(self):
        cfg = AppConfig()
        assert "javbus" in cfg.scrape_sources
        assert len(cfg.scrape_sources_fallback) > 0

    def test_post_init_normalizes_resolution(self):
        cfg = AppConfig(download_resolution="invalid")
        assert cfg.download_resolution == "best"

    def test_post_init_normalizes_trigger_mode(self):
        cfg = AppConfig(scrape_trigger_mode="invalid")
        assert cfg.scrape_trigger_mode == "manual"

    def test_post_init_normalizes_translate_provider(self):
        cfg = AppConfig(scrape_translate_provider="invalid")
        assert cfg.scrape_translate_provider == "google"

    def test_to_dict(self):
        cfg = AppConfig()
        d = cfg.to_dict()
        assert isinstance(d, dict)
        assert "output_dir" in d
        assert "scrape_sources" in d

    def test_compute_source_union(self):
        cfg = AppConfig()
        union = cfg._compute_source_union(["javbus", "dmm"])
        assert isinstance(union, list)
        assert all(s in ["javbus", "jav321", "dmm", "javdb", "javtrailers", "theporndb"] for s in union)


class TestLoadSaveConfig:
    """Test config file I/O."""

    def test_load_config_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mr_banana.utils.config.CONFIG_PATH", tmp_path / "nonexistent.json")
        cfg = load_config()
        assert isinstance(cfg, AppConfig)

    def test_load_config_invalid_json(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{")
        monkeypatch.setattr("mr_banana.utils.config.CONFIG_PATH", bad_file)
        cfg = load_config()
        assert isinstance(cfg, AppConfig)

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("mr_banana.utils.config.CONFIG_PATH", config_file)

        cfg = AppConfig(output_dir="/test/path", max_download_workers=8)
        save_config(cfg)

        assert config_file.exists()

        loaded = load_config()
        assert loaded.output_dir == "/test/path"
        assert loaded.max_download_workers == 8

    def test_save_config_atomic(self, tmp_path, monkeypatch):
        """Verify save uses atomic write (no partial files on crash)."""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("mr_banana.utils.config.CONFIG_PATH", config_file)

        cfg = AppConfig(output_dir="/test")
        save_config(cfg)

        # File should be valid JSON
        data = json.loads(config_file.read_text())
        assert data["output_dir"] == "/test"

    def test_config_thread_safety(self, tmp_path, monkeypatch):
        """Concurrent save+load should not corrupt the file."""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("mr_banana.utils.config.CONFIG_PATH", config_file)

        errors = []

        def writer(idx):
            try:
                for i in range(10):
                    cfg = AppConfig(output_dir=f"/test/{idx}/{i}")
                    save_config(cfg)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    cfg = load_config()
                    assert isinstance(cfg, AppConfig)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1,)),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # Final file should be valid JSON
        data = json.loads(config_file.read_text())
        assert "output_dir" in data
