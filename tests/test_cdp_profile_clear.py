"""Managed Chrome profile cleanup regression tests."""

import pytest

from notebooklm_tools.core.exceptions import AuthenticationError
from notebooklm_tools.utils import cdp


def test_clear_managed_profile_closes_owned_cdp_before_delete(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "Preferences").write_text("{}", encoding="utf-8")

    closed = []
    monkeypatch.setattr(
        cdp,
        "find_existing_nlm_chrome",
        lambda **kwargs: (9223, "ws://127.0.0.1:9223/devtools/browser/abc"),
    )
    monkeypatch.setattr(
        cdp,
        "close_profile_owned_cdp_browser",
        lambda url, profile: closed.append((url, profile)) or True,
    )

    cdp._clear_managed_profile_directory("work", profile_dir)

    assert closed == [("http://127.0.0.1:9223", "work")]
    assert not profile_dir.exists()


def test_clear_managed_profile_aborts_if_owned_browser_survives_close(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    remove_calls = []

    monkeypatch.setattr(
        cdp,
        "find_existing_nlm_chrome",
        lambda **kwargs: (9223, "ws://127.0.0.1:9223/devtools/browser/abc"),
    )
    monkeypatch.setattr(cdp, "close_profile_owned_cdp_browser", lambda *_args: False)
    monkeypatch.setattr(
        cdp.shutil,
        "rmtree",
        lambda *args, **kwargs: remove_calls.append((args, kwargs)),
    )

    with pytest.raises(AuthenticationError, match="Could not close browser profile 'work'"):
        cdp._clear_managed_profile_directory("work", profile_dir)

    assert remove_calls == []
    assert profile_dir.exists()


def test_clear_managed_profile_allows_browser_exit_during_close(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    discoveries = iter(
        [
            (9223, "ws://127.0.0.1:9223/devtools/browser/abc"),
            (None, None),
        ]
    )

    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **kwargs: next(discoveries))
    monkeypatch.setattr(cdp, "close_profile_owned_cdp_browser", lambda *_args: False)

    cdp._clear_managed_profile_directory("work", profile_dir)

    assert not profile_dir.exists()


def test_clear_managed_profile_fails_if_directory_stays_locked(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()

    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **kwargs: (None, None))
    monkeypatch.setattr(cdp.shutil, "rmtree", lambda *args, **kwargs: None)
    monkeypatch.setattr(cdp.time, "sleep", lambda _delay: None)

    with pytest.raises(AuthenticationError, match="Could not clear browser profile 'work'"):
        cdp._clear_managed_profile_directory("work", profile_dir)

    assert profile_dir.exists()


def test_clear_managed_profile_does_not_close_when_no_owned_browser(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()

    close_calls = []
    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **kwargs: (None, None))
    monkeypatch.setattr(
        cdp,
        "close_profile_owned_cdp_browser",
        lambda *args, **kwargs: close_calls.append(args) or True,
    )

    cdp._clear_managed_profile_directory("work", profile_dir)

    assert close_calls == []
    assert not profile_dir.exists()
