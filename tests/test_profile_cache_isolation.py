"""Regression tests for profile-scoped auth cache updates (Issue #284)."""

import json


def _save_profile(name: str, sid: str, csrf: str, session: str):
    from notebooklm_tools.core.auth import AuthManager

    manager = AuthManager(name)
    manager.save_profile(
        cookies={"SID": sid},
        csrf_token=csrf,
        session_id=session,
    )
    return manager


def test_named_profile_refresh_updates_only_that_profile():
    """Refreshing a named client must not overwrite the default account."""
    from notebooklm_tools.cli.utils import get_client
    from notebooklm_tools.core.auth import AuthTokens, save_tokens_to_cache
    from notebooklm_tools.utils.config import get_auth_cache_file, reset_config

    reset_config()
    default = _save_profile("default", "account-A", "csrf-a", "session-a")
    secondary = _save_profile("tsm", "account-B", "csrf-b", "session-b")
    save_tokens_to_cache(
        AuthTokens(
            cookies={"SID": "account-A"},
            csrf_token="csrf-a",
            session_id="session-a",
        )
    )

    client = get_client("tsm")
    client.cookies = {"SID": "account-B-refreshed"}
    client.csrf_token = "csrf-b-refreshed"
    client._session_id = "session-b-refreshed"
    client._update_cached_tokens()
    client.close()

    assert default.load_profile(force_reload=True).cookies == {"SID": "account-A"}
    refreshed = secondary.load_profile(force_reload=True)
    assert refreshed.cookies == {"SID": "account-B-refreshed"}
    assert refreshed.csrf_token == "csrf-b-refreshed"
    assert refreshed.session_id == "session-b-refreshed"
    legacy = json.loads(get_auth_cache_file().read_text(encoding="utf-8"))
    assert legacy["cookies"] == {"SID": "account-A"}


def test_named_profile_recovery_reloads_same_profile():
    """Auth recovery for a named client must not load default credentials."""
    from notebooklm_tools.cli.utils import get_client
    from notebooklm_tools.utils.config import reset_config

    reset_config()
    _save_profile("default", "account-A", "csrf-a", "session-a")
    _save_profile("tsm", "account-B", "csrf-b", "session-b")

    client = get_client("tsm")
    client.cookies = {"SID": "stale-account-B"}

    assert client._try_reload_or_headless_auth() is True
    assert client.cookies == {"SID": "account-B"}
    client.close()


def test_named_profile_load_never_falls_back_to_legacy_default():
    """A missing named profile must not inherit the legacy default account."""
    from notebooklm_tools.core.auth import AuthTokens, load_cached_tokens, save_tokens_to_cache
    from notebooklm_tools.utils.config import reset_config

    reset_config()
    _save_profile("default", "account-A", "csrf-a", "session-a")
    save_tokens_to_cache(AuthTokens(cookies={"SID": "account-A"}))

    assert load_cached_tokens(profile_name="missing") is None
