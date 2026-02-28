"""
Tests for security utilities: path traversal, SSRF protection, media roots.
"""
import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from api.security import (
    is_safe_path,
    validate_path_no_traversal,
    safe_join_path,
    validate_directory_exists,
    get_all_media_roots,
    get_library_root,
    is_path_under_roots,
)


class TestIsSafePath:
    def test_subpath_is_safe(self, tmp_path):
        sub = tmp_path / "child" / "file.txt"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.touch()
        assert is_safe_path(tmp_path, sub) is True

    def test_same_path_is_safe(self, tmp_path):
        assert is_safe_path(tmp_path, tmp_path) is True

    def test_traversal_is_unsafe(self, tmp_path):
        target = tmp_path / ".." / "etc" / "passwd"
        assert is_safe_path(tmp_path, target) is False

    def test_sibling_is_unsafe(self, tmp_path):
        sibling = tmp_path.parent / "other"
        assert is_safe_path(tmp_path, sibling) is False


class TestValidatePathNoTraversal:
    def test_clean_path(self):
        result = validate_path_no_traversal("/data/videos")
        assert result == "/data/videos"

    def test_empty_path_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_path_no_traversal("")
        assert exc_info.value.status_code == 400

    def test_dotdot_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_path_no_traversal("/data/../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_null_byte_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_path_no_traversal("/data/file\x00.txt")
        assert exc_info.value.status_code == 400

    def test_semicolon_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_path_no_traversal("/data; rm -rf /")
        assert exc_info.value.status_code == 400


class TestSafeJoinPath:
    def test_normal_join(self, tmp_path):
        result = safe_join_path(tmp_path, "child", "file.txt")
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_escape_raises(self, tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            safe_join_path(tmp_path, "..", "..", "etc", "passwd")
        assert exc_info.value.status_code == 400


class TestValidateDirectoryExists:
    def test_existing_dir(self, tmp_path):
        result = validate_directory_exists(tmp_path)
        assert result == tmp_path.resolve()

    def test_nonexistent_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_directory_exists("/nonexistent/path/xyz")
        assert exc_info.value.status_code == 400

    def test_file_not_dir_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.touch()
        with pytest.raises(HTTPException) as exc_info:
            validate_directory_exists(f)
        assert exc_info.value.status_code == 400


class TestIsPathUnderRoots:
    def test_under_root(self, tmp_path):
        child = tmp_path / "sub" / "file.mp4"
        child.parent.mkdir(parents=True)
        child.touch()
        assert is_path_under_roots(str(child), [tmp_path]) is True

    def test_not_under_root(self, tmp_path):
        other = Path("/tmp/other_path")
        assert is_path_under_roots(str(other), [tmp_path]) is False

    def test_empty_roots(self, tmp_path):
        assert is_path_under_roots(str(tmp_path / "file"), []) is False

    def test_root_itself(self, tmp_path):
        assert is_path_under_roots(str(tmp_path), [tmp_path]) is True


class TestSSRFProtection:
    """Test the _is_private_ip function used by image-proxy."""

    def test_loopback_is_private(self):
        from api.routes.library import _is_private_ip
        assert _is_private_ip("127.0.0.1") is True

    def test_localhost_is_private(self):
        from api.routes.library import _is_private_ip
        assert _is_private_ip("localhost") is True

    def test_public_ip_is_not_private(self):
        from api.routes.library import _is_private_ip
        # 8.8.8.8 (Google DNS) is public
        assert _is_private_ip("8.8.8.8") is False

    def test_unresolvable_is_blocked(self):
        from api.routes.library import _is_private_ip
        assert _is_private_ip("this.domain.does.not.exist.example") is True
