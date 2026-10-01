"""CLI integration tests for auth storage commands: status, set, resolve, relocate, and doctor."""

import json

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils.config import (
    get_auth_storage_mode,
    get_profile_dir,
    reset_config,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_isolated_env(tmp_path, monkeypatch, fake_credential_store):
    """Isolate storage dir and reset config for each test."""
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_cli_storage_status_normal_and_json(tmp_path):
    """nlm auth storage status displays mode and details in text and json formats."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid123"}, email="test@example.com")

    # Text format
    res = runner.invoke(app, ["auth", "storage", "status"])
    assert res.exit_code == 0
    assert "Profile: default" in res.output
    assert "Storage mode: file" in res.output

    # JSON format
    res_json = runner.invoke(app, ["auth", "storage", "status", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["profile"] == "default"
    assert data["mode"] == "file"
    assert data["has_legacy"] is True
    assert data["has_ciphertext"] is False
    assert data["has_conflict"] is False


def test_cli_storage_set_protected_and_file(tmp_path):
    """nlm auth storage set switches modes and reports cleanly."""
    auth = AuthManager("myprofile")
    auth.save_profile(cookies={"SID": "my_sid"}, email="user@example.com")

    # Set protected
    res = runner.invoke(app, ["auth", "storage", "set", "protected", "--profile", "myprofile"])
    assert res.exit_code == 0
    assert "Storage mode set to 'protected'" in res.output
    assert get_auth_storage_mode("myprofile") == "protected"
    assert not (get_profile_dir("myprofile") / "cookies.json").exists()
    assert (get_profile_dir("myprofile") / "credentials.enc").exists()

    # Set file
    res2 = runner.invoke(app, ["auth", "storage", "set", "file", "--profile", "myprofile"])
    assert res2.exit_code == 0
    assert "Storage mode set to 'file'" in res2.output
    assert get_auth_storage_mode("myprofile") == "file"
    assert (get_profile_dir("myprofile") / "cookies.json").exists()
    assert not (get_profile_dir("myprofile") / "credentials.enc").exists()


def test_cli_storage_set_protected_refuses_invalid_profile_name():
    """nlm auth storage set protected refuses profile names with spaces or unsupported chars."""
    res = runner.invoke(app, ["auth", "storage", "set", "protected", "--profile", "invalid name"])
    assert res.exit_code != 0
    assert "characters unsupported by protected" in res.output


def test_cli_storage_conflict_reporting_and_resolve(tmp_path):
    """nlm auth storage status reports conflict and nlm auth storage resolve resolves it."""
    auth = AuthManager("conf_cli")
    auth.save_profile(cookies={"SID": "prot_val"}, email="c@example.com")
    set_storage_mode("protected", profile_name="conf_cli")

    # Create divergent plain cookies
    cookies_path = get_profile_dir("conf_cli") / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "divergent_val"}), encoding="utf-8")

    # Status shows conflict in red and provides resolve hint
    res_status = runner.invoke(app, ["auth", "storage", "status", "--profile", "conf_cli"])
    assert res_status.exit_code == 0
    assert "Conflict detected" in res_status.output
    assert "nlm auth storage resolve" in res_status.output

    # Resolve to file
    res_resolve = runner.invoke(
        app, ["auth", "storage", "resolve", "file", "--profile", "conf_cli"]
    )
    assert res_resolve.exit_code == 0
    assert "Conflict resolved" in res_resolve.output
    assert get_auth_storage_mode("conf_cli") == "file"


def test_cli_storage_resolve_discard_inaccessible(tmp_path):
    """nlm auth storage resolve file --discard-inaccessible discards corrupt ciphertext."""
    from notebooklm_tools.utils.config import set_auth_storage_mode

    prof_dir = get_profile_dir("corrupt_cli", create=True)
    enc_path = prof_dir / "credentials.enc"
    enc_path.write_text("{corrupt_data", encoding="utf-8")
    set_auth_storage_mode("corrupt_cli", "protected")

    # Without discard-inaccessible, fails
    res_fail = runner.invoke(
        app, ["auth", "storage", "resolve", "file", "--profile", "corrupt_cli"]
    )
    assert res_fail.exit_code != 0
    assert "Cannot decrypt protected credentials" in res_fail.output
    assert "--discard-inaccessible" in res_fail.output

    # With discard-inaccessible but without confirmation, aborts
    res_abort = runner.invoke(
        app,
        [
            "auth",
            "storage",
            "resolve",
            "file",
            "--discard-inaccessible",
            "--profile",
            "corrupt_cli",
        ],
    )
    assert res_abort.exit_code != 0
    assert "Aborted" in res_abort.output

    # With discard-inaccessible and --yes, succeeds
    res_ok = runner.invoke(
        app,
        [
            "auth",
            "storage",
            "resolve",
            "file",
            "--discard-inaccessible",
            "--yes",
            "--profile",
            "corrupt_cli",
        ],
    )
    assert res_ok.exit_code == 0
    assert "Inaccessible credentials discarded" in res_ok.output
    assert not enc_path.exists()


def test_cli_storage_relocate(tmp_path):
    """nlm auth storage relocate updates installation canonical root."""
    res = runner.invoke(app, ["auth", "storage", "relocate"])
    assert res.exit_code == 0
    assert "Installation canonical root relocated to" in res.output
    assert "Installation ID:" in res.output


def test_cli_doctor_reports_storage_mode_and_conflict(tmp_path):
    """nlm doctor includes storage mode and flags conflicts."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "doc_sid"}, email="doc@example.com")
    set_storage_mode("protected", profile_name="default")

    # Plain cookies dropped to create conflict
    cookies_path = get_profile_dir("default") / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "divergent_doc_sid"}), encoding="utf-8")

    res = runner.invoke(app, ["doctor"])
    assert "Storage mode: protected" in res.output
    assert "Conflict: yes" in res.output
    assert "nlm auth storage resolve" in res.output


def test_cli_storage_resolve_clear_marker(tmp_path):
    """nlm auth storage resolve --clear-marker clears marker with --yes, refuses if quarantine non-empty."""
    from notebooklm_tools.core.auth_migration import _get_operations_dir, write_operation_marker

    write_operation_marker(
        "marker_cli", {"operation": "migrate_to_protected", "phase": "preparing"}
    )

    # Aborts without confirmation
    res_abort = runner.invoke(
        app, ["auth", "storage", "resolve", "--clear-marker", "--profile", "marker_cli"]
    )
    assert res_abort.exit_code != 0
    assert "Aborted" in res_abort.output

    # Refuses if quarantine folder has files
    q_dir = _get_operations_dir() / "quarantine" / "marker_cli_op1"
    q_dir.mkdir(parents=True)
    (q_dir / "cookies.json").write_text("{}", encoding="utf-8")

    res_refuse = runner.invoke(
        app,
        [
            "auth",
            "storage",
            "resolve",
            "--clear-marker",
            "--yes",
            "--profile",
            "marker_cli",
        ],
    )
    assert res_refuse.exit_code != 0
    assert "Cannot clear marker" in res_refuse.output
    assert "cookies.json" in res_refuse.output
    assert "cookies.json → profiles/marker_cli/cookies.json" in res_refuse.output

    # Cleans up quarantine and succeeds
    (q_dir / "cookies.json").unlink()
    q_dir.rmdir()
    res_ok = runner.invoke(
        app,
        [
            "auth",
            "storage",
            "resolve",
            "--clear-marker",
            "--yes",
            "--profile",
            "marker_cli",
        ],
    )
    assert res_ok.exit_code == 0
    assert "Operation marker cleared" in res_ok.output


def test_cli_doctor_lists_plain_and_protected_profiles(tmp_path):
    """nlm doctor lists every profile as plain or protected, plus the protect command."""
    AuthManager("work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    AuthManager("personal").save_profile(cookies={"SID": "p"}, email="p@example.com")
    set_storage_mode("protected", profile_name="work")

    res = runner.invoke(app, ["doctor"])
    assert "work: protected" in res.output
    assert "personal: plain (file mode)" in res.output
    assert "nlm auth storage set protected --profile <name>" in res.output
