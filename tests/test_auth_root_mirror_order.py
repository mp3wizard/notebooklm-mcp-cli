"""The legacy root cache cannot publish credentials a profile did not save."""

from contextlib import nullcontext

import pytest

from notebooklm_tools.core import auth, auth_migration, credential_store
from notebooklm_tools.utils import config


def test_profile_failure_does_not_update_root_mirror(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_migration, "get_raw_on_disk_storage_mode", lambda _: "file")
    monkeypatch.setattr(credential_store, "get_profile_lock", lambda _: nullcontext())
    monkeypatch.setattr(config, "get_base_default_profile", lambda: "synthetic")
    monkeypatch.setattr(config, "get_profile_dir", lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(auth, "get_cache_path", lambda: tmp_path / "auth.json")

    class FailingManager:
        def save_profile(self, **_kwargs):
            raise OSError("synthetic write failure")

    monkeypatch.setattr(auth, "get_auth_manager", lambda _: FailingManager())
    tokens = auth.AuthTokens(cookies={"SID": "synthetic"})

    with pytest.raises(OSError, match="synthetic write failure"):
        auth.save_tokens_to_cache(tokens, profile_name="synthetic")

    assert not (tmp_path / "auth.json").exists()
