"""Task 5 tests: MCP performance, caching, concurrency, and race safety.

Verifies:
- Fast hot path: 100 calls in protected mode trigger 0 helper spawns after initial decrypt
- Hanging keystore read does not block unrelated MCP operations outside _client_lock
- Single-flight cold loading: 10 concurrent threads share 1 helper spawn
- Cookie rotation compare-and-save keeps subsequent calls hot (0 reloads)
- 5 race conditions fail closed via StaleRevisionError without corrupting credentials
- Rapid writes within 1 mtime tick invalidate studio guard and AuthHealthChecker
- Automatic recovery drops browser result if disk changed during browser run
- Locked store reload raises typed error rather than continuing on stale cookies
- Env-cookie guard prevents disk writes and saved-profile recovery
- Real OS keystore benchmark with unique test service name and guaranteed cleanup
"""

import json
import os
import sys
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from notebooklm_tools.core.auth import (
    AuthTokens,
    get_auth_manager,
    load_cached_tokens,
    save_tokens_to_cache,
)
from notebooklm_tools.core.client import NotebookLMClient
from notebooklm_tools.core.credential_store import (
    BackendUnavailableError,
    CredentialStore,
    StaleRevisionError,
    clear_credential_cache,
    get_envelope_revision,
    set_backend_factory,
)
from notebooklm_tools.mcp.tools import _utils as mcp_utils
from notebooklm_tools.mcp.tools import studio as studio_tools
from notebooklm_tools.services.auth import AuthHealthChecker, get_active_auth_state
from notebooklm_tools.utils.config import get_profile_dir, reset_config, set_auth_storage_mode


@pytest.fixture(autouse=True)
def _cleanup_state():
    """Ensure in-memory cache and MCP client state are clean between tests."""
    clear_credential_cache()
    mcp_utils.reset_client()
    yield
    clear_credential_cache()
    mcp_utils.reset_client()


@pytest.fixture
def counting_worker(monkeypatch):
    """Tracks worker operations (equivalent to helper subprocess spawns in production)."""
    from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

    counts = {"get": 0, "ensure_key": 0, "set": 0, "delete": 0, "identify": 0}
    orig = CredentialWorkerClient._execute

    def counted_execute(self, request):
        op = request.get("op")
        if op in counts:
            counts[op] += 1
        return orig(self, request)

    monkeypatch.setattr(CredentialWorkerClient, "_execute", counted_execute)
    return counts


def test_hot_read_100_calls_zero_spawns(fake_credential_store, counting_worker):
    """Initial load decrypts once; 100 subsequent get_client() calls trigger 0 helper calls."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(
        cookies={"SID": "initial_cookie", "HSID": "test"},
        csrf_token="initial_csrf",
        force=True,
    )

    assert counting_worker["ensure_key"] == 1

    # First get_client(): cold read from fresh process (1 get_password call)
    clear_credential_cache()
    c1 = mcp_utils.get_client()
    assert c1.cookies == {"SID": "initial_cookie", "HSID": "test"}
    assert counting_worker["get"] == 1

    # 100 subsequent get_client() calls: hot path (<0.05 ms, 0 get_password calls)
    for _ in range(100):
        c = mcp_utils.get_client()
        assert c is c1

    assert counting_worker["get"] == 1  # Still 1! 0 additional spawns for 100 calls


def test_slow_keystore_outside_global_client_lock(fake_credential_store):
    """A slow/hanging keystore read happens outside _client_lock, allowing other operations."""
    slow_read_started = threading.Event()
    allow_slow_read_finish = threading.Event()

    def slow_load_cached_tokens(profile_name=None):
        slow_read_started.set()
        allow_slow_read_finish.wait(timeout=5.0)
        return AuthTokens(
            cookies={"SID": "slow_loaded"},
            csrf_token="slow_csrf",
            extracted_at=time.time(),
        )

    def background_client_get():
        with patch(
            "notebooklm_tools.mcp.tools._utils.load_cached_tokens",
            side_effect=slow_load_cached_tokens,
        ):
            mcp_utils.get_client()

    t = threading.Thread(target=background_client_get)
    t.start()

    assert slow_read_started.wait(timeout=2.0)

    # While keystore read is in flight outside _client_lock, another MCP operation under _client_lock succeeds
    start_time = time.monotonic()
    mcp_utils.set_query_timeout(45.0)
    elapsed = time.monotonic() - start_time
    assert elapsed < 0.1, "set_query_timeout was blocked by slow keystore read!"
    assert mcp_utils.get_query_timeout() == 45.0

    allow_slow_read_finish.set()
    t.join(timeout=2.0)


def test_single_flight_cold_loads(fake_credential_store, counting_worker):
    """10 concurrent requests for the same protected profile share 1 helper spawn."""
    set_auth_storage_mode("work", "protected")
    store = CredentialStore()
    store.write_credentials(
        "work", {"cookies": {"SID": "concurrent_cookie"}, "csrf_token": "work_csrf"}
    )
    clear_credential_cache()  # Force cold read

    assert counting_worker["ensure_key"] == 1
    counting_worker["get"] = 0

    results = []
    errors = []

    def load_task():
        try:
            payload = store.read_credentials("work")
            results.append(payload)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=load_task) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors
    assert len(results) == 10
    for r in results:
        assert r == {"cookies": {"SID": "concurrent_cookie"}, "csrf_token": "work_csrf"}

    # Single flight: exactly 1 get_password call across all 10 threads!
    assert counting_worker["get"] == 1


def test_rotation_save_then_10_calls_zero_reloads(fake_credential_store, counting_worker):
    """When cookie rotation writes new credentials, subsequent client calls see 0 reloads."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(
        cookies={"SID": "rot_init", "HSID": "1"},
        csrf_token="csrf_init",
        force=True,
    )

    clear_credential_cache()
    client = mcp_utils.get_client()

    assert counting_worker["get"] == 1

    # Simulate cookie rotation updating client and disk
    client.cookies = {"SID": "rot_updated", "HSID": "2"}
    client._update_cached_tokens()

    # Client's self revision is now current
    enc_path = get_profile_dir("default") / "credentials.enc"
    disk_rev = get_envelope_revision(enc_path)
    assert client._auth_revision == disk_rev

    # 10 subsequent get_client() calls see matching revision -> 0 reloads
    init_pw_calls = counting_worker["get"]
    for _ in range(10):
        c = mcp_utils.get_client()
        assert c is client

    assert counting_worker["get"] == init_pw_calls


# =========================================================================
# The 5 Race Tests
# =========================================================================


def test_race_1_delayed_refresh_racing_new_login(fake_credential_store):
    """Delayed background refresh fails compare-and-save if external nlm login occurred."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")

    # Initial login
    mgr.save_profile(cookies={"SID": "initial"}, csrf_token="init_csrf", force=True)
    initial_tokens = load_cached_tokens("default")
    initial_rev = initial_tokens.revision

    # New login runs in another process, updating disk revision
    mgr.save_profile(cookies={"SID": "new_login_by_user"}, csrf_token="new_csrf", force=True)
    new_tokens = load_cached_tokens("default")
    assert new_tokens.revision != initial_rev

    # Old client tries to save with stale expected_revision
    with pytest.raises(StaleRevisionError):
        mgr.save_profile(
            cookies={"SID": "stale_refreshed_cookies"},
            csrf_token="stale_csrf",
            expected_revision=initial_rev,
            force=False,
        )

    # Disk credentials must still be the new user login!
    final_tokens = load_cached_tokens("default")
    assert final_tokens.cookies == {"SID": "new_login_by_user"}


def test_race_2_default_profile_switch(fake_credential_store):
    """Switching default profile invalidates MCP client and does not overwrite wrong profile."""
    set_auth_storage_mode("work", "protected")
    set_auth_storage_mode("personal", "protected")

    get_auth_manager("work").save_profile(
        cookies={"SID": "work_cookie"}, csrf_token="work_csrf", force=True
    )
    get_auth_manager("personal").save_profile(
        cookies={"SID": "personal_cookie"}, csrf_token="personal_csrf", force=True
    )

    with patch("notebooklm_tools.utils.config.get_config") as mock_cfg:
        mock_cfg.return_value.auth.default_profile = "work"
        c_work = mcp_utils.get_client()
        assert c_work.cookies == {"SID": "work_cookie"}

    # Default profile switches to "personal"
    with patch("notebooklm_tools.utils.config.get_config") as mock_cfg:
        mock_cfg.return_value.auth.default_profile = "personal"
        c_personal = mcp_utils.get_client()
        assert c_personal.cookies == {"SID": "personal_cookie"}
        assert c_personal is not c_work


def test_race_3_mode_switch_to_file(fake_credential_store):
    """Delayed protected save fails with StaleRevisionError if profile switched to file mode."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(cookies={"SID": "prot_cookie"}, csrf_token="prot_csrf", force=True)
    rev = load_cached_tokens("default").revision

    # Switch mode to file
    set_auth_storage_mode("default", "file")
    mgr.cookies_file.write_text(json.dumps({"SID": "file_cookie"}))
    (get_profile_dir("default") / "credentials.enc").unlink()

    # Delayed save with expected_revision fails cleanly
    with pytest.raises(StaleRevisionError):
        mgr.save_profile(
            cookies={"SID": "stale_prot_attempt"},
            csrf_token="stale_csrf",
            expected_revision=rev,
            force=False,
        )

    # No ciphertext created and file cookies untouched
    assert not (get_profile_dir("default") / "credentials.enc").exists()
    assert json.loads(mgr.cookies_file.read_text()) == {"SID": "file_cookie"}


def test_race_4_profile_rename(fake_credential_store):
    """Delayed refresh targeting renamed profile fails StaleRevisionError and recreates nothing."""
    set_auth_storage_mode("old_name", "protected")
    mgr_old = get_auth_manager("old_name")
    mgr_old.save_profile(cookies={"SID": "old_cookie"}, csrf_token="old_csrf", force=True)
    rev = load_cached_tokens("old_name").revision

    # Rename profile directory
    p_old = get_profile_dir("old_name")
    p_new = get_profile_dir("new_name")
    p_old.rename(p_new)

    # Save to old profile fails because credentials.enc no longer exists there
    with pytest.raises(StaleRevisionError):
        save_tokens_to_cache(
            AuthTokens(cookies={"SID": "stale_attempt"}, csrf_token="stale_csrf"),
            profile_name="old_name",
            expected_revision=rev,
            force=False,
        )

    # Assert that after a rename, a stale save neither recreates the old profile folder nor writes plaintext
    assert not p_old.exists(), "Old profile folder was recreated by stale save!"
    assert not (p_old / "cookies.json").exists()
    assert not (p_old / "auth.json").exists()


def test_race_5_profile_delete_and_recreate(fake_credential_store):
    """Delayed refresh after profile delete fails StaleRevisionError without creating root auth.json or plaintext."""
    import shutil

    from notebooklm_tools.core.auth import get_cache_path

    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(cookies={"SID": "v1"}, csrf_token="v1_csrf", force=True)
    rev_v1 = load_cached_tokens("default").revision

    # Delete profile directory entirely
    p_dir = get_profile_dir("default")
    shutil.rmtree(p_dir)

    # Clean any root auth.json
    root_auth = get_cache_path()
    if root_auth.exists():
        root_auth.unlink()

    # Stale background save with rev_v1 against deleted profile must fail with StaleRevisionError
    # BEFORE creating directory or writing root auth.json mirror
    with pytest.raises(StaleRevisionError):
        save_tokens_to_cache(
            AuthTokens(cookies={"SID": "stale_v1"}, csrf_token="stale_csrf"),
            profile_name="default",
            expected_revision=rev_v1,
            force=False,
        )

    # Assert no root auth.json and no plaintext files appeared
    assert not root_auth.exists(), (
        "Root auth.json was recreated on stale save after profile deletion!"
    )
    assert not (p_dir / "cookies.json").exists()
    assert not (p_dir / "auth.json").exists()

    # Recreate profile with new login
    mgr.save_profile(cookies={"SID": "v2_new_account"}, csrf_token="v2_csrf", force=True)
    rev_v2 = load_cached_tokens("default").revision
    assert rev_v2 != rev_v1

    # Stale save with rev_v1 fails
    with pytest.raises(StaleRevisionError):
        save_tokens_to_cache(
            AuthTokens(cookies={"SID": "stale_v1"}, csrf_token="stale_csrf"),
            profile_name="default",
            expected_revision=rev_v1,
            force=False,
        )

    assert load_cached_tokens("default").cookies == {"SID": "v2_new_account"}


# =========================================================================
# Invalidation, Recovery, and Guards
# =========================================================================


def test_rapid_writes_within_one_mtime_tick(fake_credential_store):
    """Two writes within same mtime tick must register as a change in studio guard and AuthHealthChecker."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")

    mgr.save_profile(cookies={"SID": "write1"}, csrf_token="csrf1", force=True)
    state1 = get_active_auth_state("default")

    # Force identical file mtime on credentials.enc
    enc_path = get_profile_dir("default") / "credentials.enc"
    fixed_time = 1700000000.0
    os.utime(enc_path, (fixed_time, fixed_time))

    mgr.save_profile(cookies={"SID": "write2"}, csrf_token="csrf2", force=True)
    # Re-apply identical mtime to simulate rapid write within 1 tick
    os.utime(enc_path, (fixed_time, fixed_time))
    state2 = get_active_auth_state("default")

    assert state1 != state2, (
        "Rapid write within same mtime tick failed to produce distinct auth state!"
    )

    # Studio guard invalidation
    studio_tools._auth_guard_expires = time.monotonic() + 100.0
    studio_tools._auth_guard_mtime = state1
    assert studio_tools._get_auth_file_mtime() != studio_tools._auth_guard_mtime

    # AuthHealthChecker invalidation
    checker = AuthHealthChecker("default")
    checker._auth_state = state1
    checker._cache_ts = time.time()
    checker._report = MagicMock()
    with patch.object(checker, "_run_checks", return_value=MagicMock()) as mock_run:
        checker.check()
        assert mock_run.called, "AuthHealthChecker failed to invalidate on revision change!"


def test_automatic_recovery_drops_browser_result_on_disk_change(fake_credential_store):
    """_try_reload_or_headless_auth drops browser result if disk changed during browser run (real chain)."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(cookies={"SID": "initial"}, csrf_token="init_csrf", force=True)

    client = NotebookLMClient(
        cookies={"SID": "initial"},
        csrf_token="init_csrf",
        profile_name="default",
        auth_revision=mgr.load_profile().revision,
    )

    def fake_get_page_cookies(ws_url):
        # User logs in on disk while headless browser was running!
        mgr.save_profile(cookies={"SID": "new_user_login"}, csrf_token="new_csrf", force=True)
        return [
            {"name": k, "value": "val", "domain": ".google.com", "path": "/"}
            for k in ["SID", "HSID", "SSID", "APISID", "SAPISID"]
        ]

    # Mock low-level browser interaction so NO real Chrome process is launched,
    # but run through real _try_reload_or_headless_auth -> auth_browser -> cdp -> save_tokens_to_cache -> save_profile!
    with (
        patch("notebooklm_tools.utils.cdp.has_chrome_profile", return_value=True),
        patch("notebooklm_tools.utils.firefox.has_firefox_profile", return_value=False),
        patch("notebooklm_tools.utils.cdp.launch_chrome_process") as mock_launch,
        patch("notebooklm_tools.utils.cdp.terminate_chrome"),
        patch(
            "notebooklm_tools.utils.cdp.find_existing_nlm_chrome",
            return_value=(9223, "http://127.0.0.1:9223/json"),
        ),
        patch(
            "notebooklm_tools.utils.cdp.find_or_create_notebooklm_page",
            return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1"},
        ),
        patch(
            "notebooklm_tools.utils.cdp.get_current_url",
            return_value="https://notebooklm.google.com/",
        ),
        patch("notebooklm_tools.utils.cdp.is_logged_in", return_value=True),
        patch(
            "notebooklm_tools.utils.cdp._wait_for_page_ready",
            return_value=("<html>mock page</html>", True),
        ),
        patch("notebooklm_tools.utils.cdp.get_page_cookies", side_effect=fake_get_page_cookies),
        patch("notebooklm_tools.utils.cdp.extract_csrf_token", return_value="browser_csrf"),
        patch("notebooklm_tools.utils.cdp.extract_session_id", return_value="browser_session"),
        patch("notebooklm_tools.utils.cdp.cleanup_chrome_profile_cache"),
    ):
        recovered = client._try_reload_or_headless_auth()
        assert not mock_launch.called

    assert recovered is True
    # Kept the disk login, dropped the browser result!
    assert client.cookies == {"SID": "new_user_login"}


def test_file_mode_corrupt_cookies_keeps_existing_client():
    """In file mode, if cookies.json is corrupt or unreadable, get_client() retains existing client."""
    from notebooklm_tools.core.auth import get_cache_path

    set_auth_storage_mode("default", "file")
    mgr = get_auth_manager("default")
    mgr.save_profile(cookies={"SID": "good_file_cookie"}, csrf_token="good_csrf", force=True)

    # Ensure root auth.json does not auto-migrate from real ~/.notebooklm-mcp/auth.json
    root_auth = get_cache_path()
    root_auth.write_text("{corrupt...")

    # Initialize client
    c1 = mcp_utils.get_client()
    assert c1.cookies == {"SID": "good_file_cookie"}

    # Corrupt cookies.json (simulating non-atomic write in progress)
    mgr.cookies_file.write_text("{corrupt json ...")

    # get_client() keeps existing client rather than raising ValueError("No authentication found")
    c2 = mcp_utils.get_client()
    assert c2 is c1
    assert c2.cookies == {"SID": "good_file_cookie"}


def test_update_cached_tokens_preserves_build_label_and_base_host(fake_credential_store):
    """_update_cached_tokens with empty _bl / _base_host preserves stored values in both modes."""
    for mode in ("file", "protected"):
        set_auth_storage_mode("default", mode)
        mgr = get_auth_manager("default")
        mgr.save_profile(
            cookies={"SID": f"{mode}_cookie"},
            csrf_token="csrf1",
            build_label="BL-disk",
            base_host="notebooklm.google.com",
            force=True,
        )

        # Client with empty _bl and empty _base_host
        client = NotebookLMClient(
            cookies={"SID": f"{mode}_cookie"},
            csrf_token="csrf_new",
            profile_name="default",
            auth_revision=mgr.load_profile().revision,
        )
        assert client._bl == ""
        assert client._base_host == ""

        # Update tokens
        client._update_cached_tokens()

        # Verify metadata.json kept BL-disk and notebooklm.google.com
        meta = json.loads(mgr.metadata_file.read_text())
        assert meta.get("build_label") == "BL-disk"
        assert meta.get("base_host") == "notebooklm.google.com"


def test_login_save_profile_overwrites_base_host_with_none(fake_credential_store):
    """Explicit login via save_profile(base_host=None) still writes None (main's behavior)."""
    set_auth_storage_mode("default", "file")
    mgr = get_auth_manager("default")
    mgr.save_profile(
        cookies={"SID": "init"},
        csrf_token="csrf",
        base_host="workspace.google.com",
        force=True,
    )
    assert json.loads(mgr.metadata_file.read_text()).get("base_host") == "workspace.google.com"

    # User logs in with personal account where base_host is None
    mgr.save_profile(cookies={"SID": "personal"}, csrf_token="csrf", base_host=None, force=True)
    meta = json.loads(mgr.metadata_file.read_text())
    assert meta.get("base_host") is None


def test_locked_store_reload_raises_typed_error(fake_credential_store):
    """When StaleRevisionError triggers reload, locked store raises BackendUnavailableError."""
    set_auth_storage_mode("default", "protected")
    mgr = get_auth_manager("default")
    mgr.save_profile(cookies={"SID": "init"}, csrf_token="init_csrf", force=True)
    rev = mgr.load_profile().revision

    client = NotebookLMClient(
        cookies={"SID": "init"},
        csrf_token="init_csrf",
        profile_name="default",
        auth_revision=rev,
    )

    # Disk updated behind client so save_tokens_to_cache will raise StaleRevisionError
    mgr.save_profile(cookies={"SID": "disk_newer"}, csrf_token="disk_csrf", force=True)

    def locked_store_load(*args, **kwargs):
        raise BackendUnavailableError("Keystore locked")

    with (
        patch("notebooklm_tools.core.auth.load_cached_tokens", side_effect=locked_store_load),
        pytest.raises(BackendUnavailableError),
    ):
        client._update_cached_tokens()


def test_env_cookie_guard(monkeypatch, fake_credential_store):
    """NOTEBOOKLM_COOKIES client never touches disk or runs saved-profile recovery."""
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=env_cookie; HSID=env_hsid")

    with patch.object(NotebookLMClient, "_refresh_auth_tokens"):
        client = mcp_utils.get_client()
    assert client._is_env_auth is True

    # _update_cached_tokens is a no-op
    with patch("notebooklm_tools.core.auth.save_tokens_to_cache") as mock_save:
        client._update_cached_tokens()
        assert not mock_save.called

    # _try_reload_or_headless_auth is an immediate False
    with patch("notebooklm_tools.core.auth.load_cached_tokens") as mock_load:
        assert client._try_reload_or_headless_auth() is False
        assert not mock_load.called


def test_rotation_rate_limit_key_protected_vs_file(fake_credential_store):
    """Cookie rotation passes credentials.enc in protected mode and cookies.json in file mode."""
    set_auth_storage_mode("prot_prof", "protected")
    set_auth_storage_mode("file_prof", "file")

    get_auth_manager("prot_prof").save_profile(
        cookies={"SID": "p"}, csrf_token="p_csrf", force=True
    )
    get_auth_manager("file_prof").save_profile(
        cookies={"SID": "f"}, csrf_token="f_csrf", force=True
    )

    client_prot = NotebookLMClient(
        cookies={"SID": "p"}, csrf_token="p_csrf", profile_name="prot_prof"
    )
    client_file = NotebookLMClient(
        cookies={"SID": "f"}, csrf_token="f_csrf", profile_name="file_prof"
    )

    with patch("notebooklm_tools.core.cookie_rotation.rotate_google_cookies") as mock_rot:
        mock_rot.return_value = MagicMock(success=True)
        with patch("httpx.Client.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, text='{"SNlM0e":"csrf"}', url="https://notebooklm.google.com"
            )
            client_prot._refresh_auth_tokens()
            assert (
                mock_rot.call_args.kwargs["storage_path"]
                == get_profile_dir("prot_prof") / "credentials.enc"
            )

            client_file._refresh_auth_tokens()
            assert (
                mock_rot.call_args.kwargs["storage_path"]
                == get_profile_dir("file_prof") / "cookies.json"
            )


# =========================================================================
# Real OS Keystore Benchmark (Guaranteed Cleanup & Unique Test Service)
# =========================================================================


@pytest.mark.real_os_store
def test_real_keystore_benchmark_real_paths(monkeypatch, tmp_path):
    """Measure the 4 operations through real get_client() and save_profile() with real Keychain."""
    if not (sys.platform == "darwin" and os.environ.get("ALLOW_REAL_KEYSTORE") == "1"):
        pytest.skip("Requires macOS and ALLOW_REAL_KEYSTORE=1")

    from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

    test_service = f"test.nlm.{uuid.uuid4()}"
    monkeypatch.setenv("NOTEBOOKLM_KEYSTORE_SERVICE_NAME", test_service)
    set_backend_factory(None)  # Use real helper subprocess

    storage_dir = tmp_path / "real_storage"
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(storage_dir))
    reset_config()

    helper_spawns = 0
    orig_exec = CredentialWorkerClient._execute_in_helper

    def tracked_exec(self, request):
        nonlocal helper_spawns
        helper_spawns += 1
        return orig_exec(self, request)

    monkeypatch.setattr(CredentialWorkerClient, "_execute_in_helper", tracked_exec)

    try:
        # ==========================================
        # 1. PROTECTED MODE
        # ==========================================
        set_auth_storage_mode("default", "protected")
        mgr_prot = get_auth_manager("default")
        # Ensure installation.json exists so we isolate credentials save/load spawns
        from notebooklm_tools.core.credential_store import get_installation_identity

        get_installation_identity(storage_dir)

        # Row 1: Changed save (helper ensure_key)
        helper_spawns = 0
        t0 = time.perf_counter()
        mgr_prot.save_profile(
            cookies={"SID": "bench_cookie_val", "HSID": "bench_hsid"},
            csrf_token="bench_csrf",
            force=True,
        )
        prot_changed_save_ms = (time.perf_counter() - t0) * 1000
        prot_changed_save_spawns = helper_spawns

        # Row 2: Cold read (helper get_password)
        clear_credential_cache()
        mcp_utils.reset_client()
        helper_spawns = 0
        t0 = time.perf_counter()
        c = mcp_utils.get_client()
        prot_cold_read_ms = (time.perf_counter() - t0) * 1000
        prot_cold_read_spawns = helper_spawns
        assert c.cookies == {"SID": "bench_cookie_val", "HSID": "bench_hsid"}

        # Row 3: Hot read (100 calls through get_client())
        helper_spawns = 0
        t0 = time.perf_counter()
        for _ in range(100):
            mcp_utils.get_client()
        prot_hot_read_100_ms = (time.perf_counter() - t0) * 1000
        prot_hot_read_avg_ms = prot_hot_read_100_ms / 100
        prot_hot_read_spawns = helper_spawns

        # Row 4: No-change save (secrets unchanged)
        helper_spawns = 0
        t0 = time.perf_counter()
        mgr_prot.save_profile(
            cookies={"SID": "bench_cookie_val", "HSID": "bench_hsid"},
            csrf_token="bench_csrf",
            force=False,
        )
        prot_no_change_save_ms = (time.perf_counter() - t0) * 1000
        prot_no_change_save_spawns = helper_spawns

        assert prot_cold_read_spawns == 1, (
            f"Expected 1 spawn for cold read, got {prot_cold_read_spawns}"
        )
        assert prot_hot_read_spawns == 0, (
            f"Expected 0 spawns for hot read, got {prot_hot_read_spawns}"
        )
        assert prot_no_change_save_spawns == 0, (
            f"Expected 0 spawns for no-change save, got {prot_no_change_save_spawns}"
        )
        assert prot_changed_save_spawns == 1, (
            f"Expected 1 spawn for changed save, got {prot_changed_save_spawns}"
        )

        # ==========================================
        # 2. FILE MODE
        # ==========================================
        set_auth_storage_mode("file_prof", "file")
        mgr_file = get_auth_manager("file_prof")

        # Row 1: Changed save
        helper_spawns = 0
        t0 = time.perf_counter()
        mgr_file.save_profile(
            cookies={"SID": "file_cookie_val"},
            csrf_token="file_csrf",
            force=True,
        )
        file_changed_save_ms = (time.perf_counter() - t0) * 1000
        file_changed_save_spawns = helper_spawns

        # Switch default to file_prof for get_client() testing
        with patch("notebooklm_tools.utils.config.get_config") as mock_cfg:
            mock_cfg.return_value.auth.default_profile = "file_prof"
            mcp_utils.reset_client()

            # Row 2: Cold read
            helper_spawns = 0
            t0 = time.perf_counter()
            c_file = mcp_utils.get_client()
            file_cold_read_ms = (time.perf_counter() - t0) * 1000
            file_cold_read_spawns = helper_spawns
            assert c_file.cookies == {"SID": "file_cookie_val"}

            # Row 3: Hot read (100 calls)
            helper_spawns = 0
            t0 = time.perf_counter()
            for _ in range(100):
                mcp_utils.get_client()
            file_hot_read_100_ms = (time.perf_counter() - t0) * 1000
            file_hot_read_avg_ms = file_hot_read_100_ms / 100
            file_hot_read_spawns = helper_spawns

            # Row 4: No-change save
            helper_spawns = 0
            t0 = time.perf_counter()
            mgr_file.save_profile(
                cookies={"SID": "file_cookie_val"},
                csrf_token="file_csrf",
                force=False,
            )
            file_no_change_save_ms = (time.perf_counter() - t0) * 1000
            file_no_change_save_spawns = helper_spawns

        assert file_cold_read_spawns == 0
        assert file_hot_read_spawns == 0
        assert file_no_change_save_spawns == 0
        assert file_changed_save_spawns == 0

        print("\n================ REAL KEYCHAIN BENCHMARK RESULTS ================")
        print(f"Test Service: {test_service} (isolated, cleaned up)")
        print("| Operation               | Protected (spawns / ms)   | File (spawns / ms)        |")
        print("|-------------------------|---------------------------|---------------------------|")
        print(
            f"| Cold read               | {prot_cold_read_spawns} spawn / {prot_cold_read_ms:>8.2f} ms | {file_cold_read_spawns} spawns / {file_cold_read_ms:>7.2f} ms |"
        )
        print(
            f"| Hot read (100 calls avg)| {prot_hot_read_spawns} spawns / {prot_hot_read_avg_ms:>7.4f} ms | {file_hot_read_spawns} spawns / {file_hot_read_avg_ms:>7.4f} ms |"
        )
        print(
            f"| No-change save          | {prot_no_change_save_spawns} spawns / {prot_no_change_save_ms:>7.2f} ms | {file_no_change_save_spawns} spawns / {file_no_change_save_ms:>7.2f} ms |"
        )
        print(
            f"| Changed save            | {prot_changed_save_spawns} spawn / {prot_changed_save_ms:>8.2f} ms | {file_changed_save_spawns} spawns / {file_changed_save_ms:>7.2f} ms |"
        )
        print("=================================================================\n")

    finally:
        # Guaranteed cleanup of test Keychain items
        try:
            store = CredentialStore(storage_dir=storage_dir, service_name=test_service)
            store.delete_credentials("default")
        except Exception:
            pass
