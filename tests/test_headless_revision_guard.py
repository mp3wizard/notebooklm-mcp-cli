"""Headless recovery must not overwrite a newer profile login."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from notebooklm_tools.core import auth, auth_migration, credential_store
from notebooklm_tools.utils import cdp, config


def test_headless_wrapper_passes_captured_revision(tmp_path, monkeypatch):
    before = SimpleNamespace(revision="rev-old", extracted_at=1, cookies={"SID": "old"})
    monkeypatch.setattr(auth, "load_cached_tokens", lambda **_: before)
    monkeypatch.setattr(config, "get_storage_dir", lambda: tmp_path)
    launch = Mock()
    monkeypatch.setattr(cdp, "_run_headless_auth_unlocked", launch)

    cdp.run_headless_auth(profile_name="synthetic")
    assert launch.call_args.kwargs["expected_revision"] == "rev-old"
    assert launch.call_args.kwargs["expected_file_fingerprint"] == (
        auth.auth_state_fingerprint(before)
    )


def test_file_mode_state_changed_aborts_save(tmp_path, monkeypatch):
    old = auth.AuthTokens(cookies={"SID": "old"})
    newer = auth.AuthTokens(cookies={"SID": "new"})
    monkeypatch.setattr(auth_migration, "get_raw_on_disk_storage_mode", lambda _: "file")
    monkeypatch.setattr(credential_store, "get_profile_lock", lambda _: nullcontext())
    monkeypatch.setattr(config, "get_base_default_profile", lambda: "synthetic")

    class Manager:
        save_profile = Mock()

        def profile_exists(self):
            return True

        def load_profile(self, force_reload=False):
            return newer

    manager = Manager()
    monkeypatch.setattr(auth, "get_auth_manager", lambda _: manager)
    with pytest.raises(credential_store.StaleRevisionError):
        auth.save_tokens_to_cache(
            old,
            profile_name="synthetic",
            expected_file_fingerprint=auth.auth_state_fingerprint(old),
            force=False,
        )
    manager.save_profile.assert_not_called()
