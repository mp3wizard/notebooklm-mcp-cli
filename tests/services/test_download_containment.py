"""Security tests: MCP downloads must stay inside an approved directory.

Covers GHSA-92q4-9x75-55rf. ``validate_output_path`` used a denylist, so every
sensitive path that was not on the list stayed writable: ``~/.zshenv``,
``~/.codex/AGENTS.md``, ``.git/hooks/pre-commit`` and many more. A prompt
injection could therefore land artifact bytes on a file that another program
later executes or reads as instructions.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notebooklm_tools.mcp.tools import downloads as mcp_downloads
from notebooklm_tools.services.downloads import (
    download_all,
    download_async,
    download_sync,
    resolve_download_root,
    validate_output_path,
)
from notebooklm_tools.services.errors import ValidationError

# Paths from the advisory that the denylist let through.
REPORTED_BYPASSES = (
    ".zshenv",
    ".zprofile",
    ".bash_logout",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".docker/config.json",
    ".local/bin/git",
    ".cursor/skills/nlm-skill/SKILL.md",
    ".gemini/GEMINI.md",
    ".codex/AGENTS.md",
    ".agents/skills/x/SKILL.md",
    ".cline/skills/nlm-skill/SKILL.md",
    "Library/LaunchAgents/com.evil.plist",
    "project/.git/hooks/pre-commit",
)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Isolate HOME and app storage so tests never touch the real machine."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(home / ".notebooklm-mcp-cli"))
    monkeypatch.delenv("NOTEBOOKLM_DOWNLOAD_DIR", raising=False)
    return home


class TestResolveDownloadRoot:
    def test_uses_downloads_subfolder_when_downloads_exists(self, fake_home):
        (fake_home / "Downloads").mkdir()

        assert resolve_download_root() == fake_home / "Downloads" / "gemini-notebook"

    def test_falls_back_to_app_storage_when_downloads_missing(self, fake_home):
        # Headless Linux, containers, and relocated Windows Known Folders.
        assert resolve_download_root() == fake_home / ".notebooklm-mcp-cli" / "downloads"

    def test_never_creates_a_downloads_folder_that_did_not_exist(self, fake_home):
        resolve_download_root()

        assert not (fake_home / "Downloads").exists()

    def test_env_override_wins(self, fake_home, monkeypatch, tmp_path):
        custom = tmp_path / "custom-downloads"
        monkeypatch.setenv("NOTEBOOKLM_DOWNLOAD_DIR", str(custom))

        assert resolve_download_root() == custom


class TestEnforcedRootRejectsEscapes:
    @pytest.mark.parametrize("relative", REPORTED_BYPASSES)
    def test_rejects_every_path_from_the_advisory(self, fake_home, relative):
        target = fake_home / relative

        with pytest.raises(ValidationError):
            validate_output_path(str(target), enforce_root=True)

    def test_rejects_parent_traversal(self, fake_home):
        escape = resolve_download_root() / ".." / ".." / ".zshenv"

        with pytest.raises(ValidationError):
            validate_output_path(str(escape), enforce_root=True)

    def test_rejects_symlink_pointing_outside_root(self, fake_home):
        root = resolve_download_root()
        root.mkdir(parents=True)
        outside = fake_home / "outside"
        outside.mkdir()
        (root / "escape").symlink_to(outside, target_is_directory=True)

        with pytest.raises(ValidationError):
            validate_output_path(str(root / "escape" / "artifact.md"), enforce_root=True)

    def test_rejects_absolute_path_outside_root(self, fake_home, tmp_path):
        with pytest.raises(ValidationError):
            validate_output_path(str(tmp_path / "elsewhere" / "a.md"), enforce_root=True)


class TestEnforcedRootAllowsLegitimateDownloads:
    def test_allows_path_inside_root(self, fake_home):
        target = resolve_download_root() / "podcast.m4a"

        assert validate_output_path(str(target), enforce_root=True) == str(target)

    def test_allows_nested_path_inside_root(self, fake_home):
        target = resolve_download_root() / "My Notebook" / "report.md"

        assert validate_output_path(str(target), enforce_root=True) == str(target)

    def test_anchors_relative_path_to_root_instead_of_cwd(self, fake_home):
        # An agent saying "report.md" must not write into the process CWD.
        resolved = validate_output_path("report.md", enforce_root=True)

        assert resolved == str(resolve_download_root() / "report.md")

    def test_returns_the_path_that_callers_must_write_to(self, fake_home):
        resolved = validate_output_path("sub/../report.md", enforce_root=True)

        assert resolved == str(resolve_download_root() / "report.md")
        assert Path(resolved).is_absolute()


class TestCliBehaviourUnchanged:
    """The CLI user types their own path, so containment does not apply there."""

    def test_allows_arbitrary_path_without_enforcement(self, fake_home, tmp_path):
        target = tmp_path / "anywhere" / "report.md"

        assert validate_output_path(str(target)) == str(target)

    def test_still_blocks_sensitive_directories_without_enforcement(self, fake_home):
        with pytest.raises(ValidationError):
            validate_output_path(str(fake_home / ".ssh" / "artifact.md"))

    @pytest.mark.parametrize("relative", [".zshenv", ".netrc", ".codex/AGENTS.md"])
    def test_denylist_now_also_covers_the_reported_paths(self, fake_home, relative):
        with pytest.raises(ValidationError):
            validate_output_path(str(fake_home / relative))

    def test_env_download_dir_still_confines_the_cli(self, fake_home, monkeypatch, tmp_path):
        confined = tmp_path / "confined"
        monkeypatch.setenv("NOTEBOOKLM_DOWNLOAD_DIR", str(confined))

        with pytest.raises(ValidationError):
            validate_output_path(str(tmp_path / "outside.md"))


# ---------------------------------------------------------------------------
# Wiring: the hardened validator only protects anyone if callers turn it on.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.download_report.return_value = "saved.md"
    client.download_audio = AsyncMock(return_value="saved.m4a")
    return client


class TestServiceEnforcement:
    def test_download_sync_rejects_path_outside_root(self, fake_home, mock_client, tmp_path):
        with pytest.raises(ValidationError):
            download_sync(
                mock_client, "nb-1", "report", str(tmp_path / "evil.md"), enforce_root=True
            )

    def test_download_sync_hands_the_validated_path_to_the_client(self, fake_home, mock_client):
        download_sync(mock_client, "nb-1", "report", "report.md", enforce_root=True)

        expected = str(resolve_download_root() / "report.md")
        assert expected in mock_client.download_report.call_args[0]

    def test_download_sync_without_enforcement_keeps_the_caller_path(
        self, fake_home, mock_client, tmp_path
    ):
        target = tmp_path / "report.md"

        download_sync(mock_client, "nb-1", "report", str(target))

        assert str(target) in mock_client.download_report.call_args[0]

    def test_download_async_rejects_path_outside_root(self, fake_home, mock_client, tmp_path):
        with pytest.raises(ValidationError):
            asyncio.run(
                download_async(
                    mock_client, "nb-1", "audio", str(tmp_path / "evil.m4a"), enforce_root=True
                )
            )

    def test_download_all_rejects_output_dir_outside_root(self, fake_home, mock_client, tmp_path):
        with pytest.raises(ValidationError):
            asyncio.run(
                download_all(
                    mock_client, "nb-1", output_dir=str(tmp_path / "evil"), enforce_root=True
                )
            )


class TestMcpToolsOptIn:
    """Every model-driven download path must enable containment."""

    def test_download_artifact_enforces_root(self):
        stub = AsyncMock(return_value={"artifact_type": "report", "path": "/x/report.md"})
        with (
            patch.object(mcp_downloads.downloads_service, "download_async", stub),
            patch.object(mcp_downloads, "get_client", return_value=MagicMock()),
        ):
            mcp_downloads.download_artifact("nb-1", "report", "report.md")

        assert stub.call_args.kwargs["enforce_root"] is True

    def test_download_all_artifacts_enforces_root(self):
        stub = AsyncMock(
            return_value={
                "notebook_id": "nb-1",
                "notebook_title": "N",
                "output_dir": "/x",
                "items": [],
                "skipped": [],
                "total_artifacts": 0,
                "downloaded": 0,
                "failed": 0,
            }
        )
        with (
            patch.object(mcp_downloads.downloads_service, "download_all", stub),
            patch.object(mcp_downloads, "get_client", return_value=MagicMock()),
        ):
            mcp_downloads.download_all_artifacts("nb-1")

        assert stub.call_args.kwargs["enforce_root"] is True
