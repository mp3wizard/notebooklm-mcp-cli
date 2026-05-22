"""Tests for snap browser detection and profile directory routing."""

from pathlib import Path
from unittest.mock import patch
import pytest

from notebooklm_tools.utils.cdp import _is_snap_browser, get_snap_common_dir
from notebooklm_tools.utils.config import get_snap_chrome_profile_dir


def test_is_snap_browser_direct_path():
    """Paths starting with or containing /snap/ are detected as snap browsers."""
    assert _is_snap_browser("/snap/bin/chromium") is True
    assert _is_snap_browser("/var/lib/snapd/snap/bin/google-chrome") is True
    assert _is_snap_browser("") is False


def test_is_snap_browser_symlink(tmp_path):
    """Symlinks resolving to a path containing /snap/ are detected as snaps."""
    snap_dir = tmp_path / "snap" / "bin"
    snap_dir.mkdir(parents=True)
    real_binary = snap_dir / "chromium"
    real_binary.touch()

    bin_dir = tmp_path / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    symlink = bin_dir / "chromium"
    symlink.symlink_to(real_binary)

    # Mock Path.resolve to simulate a resolved snap path
    with patch.object(Path, "resolve", return_value=Path("/snap/chromium/current/usr/bin/chromium")):
        assert _is_snap_browser(str(symlink)) is True


def test_is_snap_browser_non_snap():
    """Standard non-snap browser paths are not detected as snaps."""
    assert _is_snap_browser("/usr/bin/google-chrome") is False
    assert _is_snap_browser("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") is False


def test_get_snap_common_dir_non_snap():
    """Non-snap browser paths return None for snap common directory."""
    assert get_snap_common_dir("/usr/bin/google-chrome") is None


def test_get_snap_common_dir_from_resolved_parts():
    """Extract snap common directory name from path parts."""
    with patch.object(Path, "resolve", return_value=Path("/snap/chromium/current/usr/bin/chromium")):
        with patch("pathlib.Path.home", return_value=Path("/home/user")):
            common_dir = get_snap_common_dir("/usr/bin/chromium")
            assert common_dir == Path("/home/user/snap/chromium/common")


def test_get_snap_common_dir_fallback(tmp_path):
    """If parts extraction doesn't match, fallback checks existing snap common dirs."""
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True)
    
    snap_common = fake_home / "snap" / "chromium" / "common"
    snap_common.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=fake_home):
        with patch.object(Path, "resolve", return_value=Path("/snap/bin/browser")):
            common_dir = get_snap_common_dir("/snap/bin/browser")
            assert common_dir == snap_common


def test_get_snap_chrome_profile_dir_auto_detect(tmp_path):
    """get_snap_chrome_profile_dir auto-detects existing snap common dirs."""
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True)

    chrome_common = fake_home / "snap" / "google-chrome" / "common"
    chrome_common.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=fake_home):
        profile_dir = get_snap_chrome_profile_dir(profile_name="test_profile")
        expected_dir = chrome_common / "notebooklm-mcp-cli" / "chrome-profiles" / "test_profile"
        assert profile_dir == expected_dir
        assert expected_dir.exists()


def test_get_snap_chrome_profile_dir_fallback(tmp_path):
    """If no snap directories exist, fallback to chromium common path and create it."""
    fake_home = tmp_path / "home" / "user"
    fake_home.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=fake_home):
        profile_dir = get_snap_chrome_profile_dir(profile_name="test_profile")
        expected_dir = fake_home / "snap" / "chromium" / "common" / "notebooklm-mcp-cli" / "chrome-profiles" / "test_profile"
        assert profile_dir == expected_dir
        assert expected_dir.exists()
