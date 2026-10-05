"""Configuration management for NotebookLM MCP CLI.

Uses ~/.notebooklm-mcp-cli/ for all data (config, profiles, Chrome profile).
Supports automatic migration from old locations:
- ~/.notebooklm-mcp/ (old MCP-only location, pre-0.2.13)
- ~/.nlm/ (old CLI location)
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from pydantic import BaseModel, Field

# =============================================================================
# Storage Location
# =============================================================================

STORAGE_DIR_NAME = ".notebooklm-mcp-cli"


def get_home_dir() -> Path:
    """Resolve a writable home anchor without failing at module import.

    Service and hermetic runtimes can intentionally omit HOME/USERPROFILE. The
    CLI still needs deterministic local state in that case, but importing the
    package must not crash before an explicit NOTEBOOKLM_MCP_CLI_PATH override
    can be honored.
    """
    try:
        return Path.home()
    except RuntimeError:
        if configured := str(os.environ.get("NOTEBOOKLM_MCP_CLI_PATH") or "").strip():
            return Path(configured).parent
        for name in ("USERPROFILE", "HOME"):
            value = str(os.environ.get(name) or "").strip()
            if value:
                return Path(value)
        return Path.cwd() / ".notebooklm-home"


def safe_mkdir(
    path: Path, *, parents: bool = False, exist_ok: bool = True, mode: int = 0o777
) -> None:
    """Create a directory, working around Python 3.14 Windows regression.

    On Python 3.14 + Windows, ``pathlib.mkdir(parents=True, exist_ok=True)``
    can raise ``FileExistsError`` (WinError 183) even when the directory
    already exists.  This wrapper catches that specific failure.
    See: https://github.com/jacob-bd/gemini-notebook-mcp-cli/issues/169
    """
    try:
        path.mkdir(parents=parents, exist_ok=exist_ok, mode=mode)
    except FileExistsError:
        if path.is_dir():
            return
        raise
    except PermissionError:
        raise PermissionError(
            f"Cannot write to {path} — permission denied.\n"
            f'On Windows, fix with: icacls "{path.parent}" /grant %USERNAME%:(OI)(CI)F /t'
        ) from None


_ALLOWED_BASE_HOSTS = {
    "notebooklm.google.com",
    "notebook.google.com",
    "notebooklm.cloud.google.com",
    "notebook.cloud.google.com",
    "vertexaisearch.cloud.google.com",
}


def get_base_url(profile_host: str | None = None) -> str:
    """Get the NotebookLM base URL.

    Resolution order:
      1. NOTEBOOKLM_BASE_URL env var, if set.
      2. profile_host, if given and it's a recognized host (issue #269: the
         host a signed-in account was last seen on, e.g. after Google's
         notebook.google.com rebrand rollout).
      3. The default personal URL (https://notebooklm.google.com).

    Set NOTEBOOKLM_BASE_URL to override, e.g. for enterprise:
        export NOTEBOOKLM_BASE_URL=https://notebooklm.cloud.google.com
    """
    from urllib.parse import urlparse

    env_override = os.environ.get("NOTEBOOKLM_BASE_URL")
    if env_override:
        url = env_override.rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_BASE_HOSTS:
            raise ValueError(
                f"NOTEBOOKLM_BASE_URL must use https and one of: {_ALLOWED_BASE_HOSTS}. Got: {url}"
            )
        return f"{parsed.scheme}://{parsed.netloc}"

    if profile_host and profile_host in _ALLOWED_BASE_HOSTS:
        return f"https://{profile_host}"

    url = "https://notebooklm.google.com"
    return url


def get_enterprise_project_id() -> str:
    """Get GCP Project ID for Gemini Notebook Enterprise (from NOTEBOOKLM_PROJECT_ID or default)."""
    return os.environ.get("NOTEBOOKLM_PROJECT_ID", "").strip()


def get_enterprise_location() -> str:
    """Get GCP Location/Region for Gemini Notebook Enterprise (from NOTEBOOKLM_LOCATION or default 'global').

    Supported locations include: 'global', 'us', 'eu', or specific regions.
    """
    loc = os.environ.get("NOTEBOOKLM_LOCATION", "").strip()
    return loc if loc else "global"


def get_notebook_url(notebook_id: str, profile_host: str | None = None) -> str:
    """Build the browser URL for a notebook on the configured host."""
    base_url = get_base_url(profile_host)
    host = (urlparse(base_url).hostname or "").lower()
    if host not in {
        "notebooklm.cloud.google.com",
        "notebook.cloud.google.com",
        "vertexaisearch.cloud.google.com",
    }:
        return f"{base_url}/notebook/{quote(notebook_id, safe='')}"

    location = get_enterprise_location()
    prefix = (
        f"/notebooklm/{location}" if host == "vertexaisearch.cloud.google.com" else f"/{location}"
    )
    url = f"{base_url}{prefix}/notebook/{quote(notebook_id, safe='')}"
    project_id = get_enterprise_project_id()
    return f"{url}?project={quote(project_id, safe='')}" if project_id else url


def get_default_language() -> str:
    """Get default language from NOTEBOOKLM_HL env var, falling back to 'en'.

    Mirrors NotebookLM web behavior: when creating artifacts, the notebook's
    interface language (hl) is used as the default, so users don't need to
    specify --language on every command.
    """
    return os.environ.get("NOTEBOOKLM_HL", "en")


def get_storage_dir() -> Path:
    """Get the main storage directory (~/.notebooklm-mcp-cli/).

    Returns the path, creating it if needed.
    """
    if env_path := os.environ.get("NOTEBOOKLM_MCP_CLI_PATH"):
        storage_dir = Path(env_path)
    else:
        storage_dir = get_home_dir() / STORAGE_DIR_NAME

    safe_mkdir(storage_dir, mode=0o700)
    return storage_dir


def get_config_dir() -> Path:
    """Get the configuration directory path (alias for get_storage_dir)."""
    return get_storage_dir()


def get_legacy_storage_dir() -> Path:
    """Get the legacy storage directory (~/.notebooklm-mcp/)."""
    return get_home_dir() / ".notebooklm-mcp"


def get_data_dir() -> Path:
    """Get the data directory path (alias for get_storage_dir)."""
    return get_storage_dir()


def get_profiles_dir(create: bool = True) -> Path:
    """Get the profiles directory path."""
    profiles_dir = get_storage_dir() / "profiles"
    if create:
        safe_mkdir(profiles_dir)
    return profiles_dir


def get_profile_dir(profile_name: str = "default", create: bool = True) -> Path:
    """Get directory for a specific profile."""
    validate_profile_name(profile_name, strict=False)
    profile_dir = get_profiles_dir(create=create) / profile_name
    if create:
        safe_mkdir(profile_dir, parents=True)
    return profile_dir


def get_chrome_profile_dir(profile_name: str = "default") -> Path:
    """Get Chrome profile directory for automated auth.

    Each NLM profile gets its own Chrome user-data-dir so different
    Google accounts can be used for different profiles.

    For backward compatibility, the "default" profile uses the old
    chrome-profile/ directory if it exists, keeping single-profile
    users' experience unchanged.
    """
    storage = get_storage_dir()

    # Backward compatibility: use old location for default profile if it exists
    if profile_name == "default":
        old_chrome_dir = storage / "chrome-profile"
        if old_chrome_dir.exists():
            return old_chrome_dir

    # New multi-profile structure
    chrome_dir = storage / "chrome-profiles" / profile_name
    safe_mkdir(chrome_dir, parents=True)
    return chrome_dir


def get_snap_chrome_profile_dir(
    profile_name: str = "default",
    snap_common: Path | None = None,
) -> Path:
    """Get a snap-accessible Chrome profile directory.

    Snap packages (like snap Chromium) are confined by AppArmor and can
    only write to ~/snap/<snap-name>/common/. This function returns a
    profile directory inside that accessible location.

    Args:
        profile_name: NLM profile name
        snap_common: Path to snap common directory (e.g., ~/snap/chromium/common)
                     If None, auto-detects from installed snaps.

    Returns:
        Path to a snap-accessible Chrome profile directory.
    """
    if snap_common is None:
        # Auto-detect snap common directory
        for snap_name in ("chromium", "google-chrome"):
            candidate = get_home_dir() / "snap" / snap_name / "common"
            if candidate.exists():
                snap_common = candidate
                break

    if snap_common is None:
        # Fallback: use chromium common dir (create if needed)
        snap_common = get_home_dir() / "snap" / "chromium" / "common"
        safe_mkdir(snap_common, parents=True)

    chrome_dir = snap_common / "notebooklm-mcp-cli" / "chrome-profiles" / profile_name
    safe_mkdir(chrome_dir, parents=True)
    return chrome_dir


def get_firefox_profile_dir(profile_name: str = "default") -> Path:
    """Get the persistent Firefox profile directory for automated auth."""
    firefox_dir = get_storage_dir() / "firefox-profiles" / profile_name
    safe_mkdir(firefox_dir, parents=True, mode=0o700)
    firefox_dir.chmod(0o700)
    return firefox_dir


def get_config_file() -> Path:
    """Get the config file path."""
    return get_storage_dir() / "config.toml"


def get_auth_cache_file() -> Path:
    """Get the auth cache file path (for MCP compatibility)."""
    return get_storage_dir() / "auth.json"


# =============================================================================
# Migration Support
# =============================================================================

# Old locations are resolved per call (not at import) so they follow the current home.


def get_old_chrome_profiles() -> list[Path]:
    """Old locations for Chrome profiles (checked for migration)."""
    return [
        get_legacy_storage_dir() / "chrome-profile",  # Old MCP (pre-0.2.13)
        get_home_dir() / ".nlm" / "chrome-profile",  # Old CLI
    ]


def get_old_auth_locations() -> list[Path]:
    """Old locations for auth.json (checked for migration)."""
    return [
        get_legacy_storage_dir() / "auth.json",  # Old MCP (pre-0.2.13)
    ]


# Old locations for aliases
OLD_ALIAS_LOCATIONS: list[Path] = []

# Try to add old CLI alias location (platformdirs-based)
try:
    from platformdirs import user_config_dir

    OLD_ALIAS_LOCATIONS.append(Path(user_config_dir("nlm")) / "aliases.json")
except ImportError:
    pass


def check_migration_sources() -> dict[str, list[Path]]:
    """Check for existing data that can be migrated.

    Returns dict with:
        - chrome_profiles: list of existing Chrome profile directories
        - auth_files: list of existing auth.json files
        - aliases: list of existing alias files
    """
    result = {
        "chrome_profiles": [],
        "auth_files": [],
        "aliases": [],
    }

    for profile_path in get_old_chrome_profiles():
        if profile_path.exists() and profile_path.is_dir():
            result["chrome_profiles"].append(profile_path)

    for auth_path in get_old_auth_locations():
        if auth_path.exists() and auth_path.is_file():
            result["auth_files"].append(auth_path)

    for alias_path in OLD_ALIAS_LOCATIONS:
        if alias_path.exists() and alias_path.is_file():
            result["aliases"].append(alias_path)

    return result


def migrate_auth_file(source_path: Path, dry_run: bool = True) -> str | None:
    """Migrate auth.json from old location.

    Args:
        source_path: Path to the old auth.json file
        dry_run: If True, only report what would be done

    Returns:
        Action description if migration was done, None if skipped
    """
    configured_default = get_config().auth.default_profile
    if get_auth_storage_mode(configured_default) == "protected":
        return None

    new_auth = get_storage_dir() / "auth.json"

    if new_auth.exists():
        return None  # Already have auth, don't overwrite

    action = f"Copy auth tokens from {source_path}"
    if not dry_run:
        shutil.copy2(source_path, new_auth)

    return action


def migrate_aliases(source_path: Path, dry_run: bool = True) -> str | None:
    """Migrate aliases from old location.

    Args:
        source_path: Path to the old aliases.json file
        dry_run: If True, only report what would be done

    Returns:
        Action description if migration was done, None if skipped
    """
    new_aliases = get_storage_dir() / "aliases.json"

    if new_aliases.exists():
        return None  # Already have aliases, don't overwrite

    action = f"Copy aliases from {source_path}"
    if not dry_run:
        shutil.copy2(source_path, new_aliases)

    return action


def migrate_chrome_profile(source_path: Path, dry_run: bool = True) -> str | None:
    """Migrate Chrome profile from old location.

    Note: Chrome profile copy provides one-click login experience.
    User will see account chooser but won't need to enter password.

    Args:
        source_path: Path to the old chrome-profile directory
        dry_run: If True, only report what would be done

    Returns:
        Action description if migration was done, None if skipped
    """
    new_chrome = get_storage_dir() / "chrome-profile"

    if new_chrome.exists():
        return None  # Already have a Chrome profile, don't overwrite

    action = f"Copy Chrome profile from {source_path}"
    if not dry_run:
        shutil.copytree(source_path, new_chrome)

    return action


def run_migration(dry_run: bool = True, prefer_source: str | None = None) -> list[str]:
    """Run migration from old locations.

    Args:
        dry_run: If True, only report what would be done
        prefer_source: If multiple Chrome profiles exist, prefer "cli" or "mcp"

    Returns:
        List of actions taken (or that would be taken)
    """
    actions = []
    sources = check_migration_sources()

    # Migrate auth.json (first one found wins)
    for auth_path in sources["auth_files"]:
        action = migrate_auth_file(auth_path, dry_run)
        if action:
            actions.append(action)
            break  # Only migrate once

    # Migrate aliases (first one found wins)
    for alias_path in sources["aliases"]:
        action = migrate_aliases(alias_path, dry_run)
        if action:
            actions.append(action)
            break  # Only migrate once

    # Migrate Chrome profile
    if sources["chrome_profiles"]:
        # If user has preference, try that first
        if prefer_source == "cli":
            # Prefer CLI location
            sources["chrome_profiles"].sort(key=lambda p: 0 if ".nlm" in str(p) else 1)
        elif prefer_source == "mcp":
            # Prefer MCP location
            sources["chrome_profiles"].sort(key=lambda p: 0 if ".notebooklm-mcp" in str(p) else 1)

        # Use the first available
        for profile_path in sources["chrome_profiles"]:
            action = migrate_chrome_profile(profile_path, dry_run)
            if action:
                actions.append(action)
                break  # Only migrate once

    return actions


def auto_migrate_if_needed() -> list[str]:
    """Automatically migrate data from old locations if new location is empty.

    This is called automatically when accessing storage to ensure seamless
    upgrade experience. Users don't need to do anything manually.

    Returns:
        List of migration actions performed (empty if nothing migrated)
    """
    configured_default = get_config().auth.default_profile
    if get_auth_storage_mode(configured_default) == "protected":
        return []

    storage = get_storage_dir()

    # Check if new location already has data
    has_auth = (storage / "auth.json").exists()
    has_chrome = (storage / "chrome-profile").exists() or (storage / "chrome-profiles").exists()

    # If we already have data, no migration needed
    if has_auth and has_chrome:
        return []

    # Run migration (not dry run)
    return run_migration(dry_run=False)


# =============================================================================
# Configuration Models
# =============================================================================


class ConfigError(Exception):
    """Raised when configuration file is corrupt or invalid."""


class OutputConfig(BaseModel):
    """Output formatting configuration."""

    format: str = Field(default="table", description="Default output format: table, json, compact")
    color: bool = Field(default=True, description="Enable colored output")
    short_ids: bool = Field(default=True, description="Show abbreviated IDs by default")


class AuthConfig(BaseModel):
    """Authentication configuration."""

    browser: str = Field(
        default="auto",
        description=(
            "Browser for auth: auto, chrome, arc, brave, dia, comet, edge, edge-beta, chromium, firefox, vivaldi, opera"
        ),
    )
    browser_path: str = Field(
        default="",
        description="Optional path to a Chromium-compatible browser executable",
    )
    default_profile: str = Field(default="default", description="Default profile name")


class Config(BaseModel):
    """Main configuration model."""

    output: OutputConfig = Field(default_factory=OutputConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


_RESERVED_DEVICE_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


def validate_profile_name(profile_name: str, strict: bool = True) -> None:
    """Validate profile name for filesystem and keystore safety.

    - Base safety check (strict=False, used everywhere in file mode):
      Rejects empty names, non-string, NUL bytes, path separators ('/' and '\\'),
      and path traversal ('..' or '.').
    - Strict check (strict=True, used for protected mode and keystore accounts):
      Also rejects whitespace, enforces character set ^[a-zA-Z0-9_\\-\\.]+$,
      reserved device names, and case-insensitive collisions with existing profiles.
    """
    import re

    if not profile_name or not isinstance(profile_name, str):
        raise ValueError("Profile name cannot be empty")

    if "\0" in profile_name:
        raise ValueError(f"Profile name cannot contain NUL bytes: '{profile_name}'")

    if "/" in profile_name or "\\" in profile_name or profile_name in (".", ".."):
        raise ValueError(
            f"Profile name cannot contain path traversal or separators: '{profile_name}'"
        )
    if (
        "/." in profile_name
        or "../" in profile_name
        or "..\\" in profile_name
        or ".\\" in profile_name
        or "/.." in profile_name
        or "\\.." in profile_name
    ):
        raise ValueError(
            f"Profile name cannot contain path traversal or separators: '{profile_name}'"
        )

    if not strict:
        return

    stripped = profile_name.strip()
    if stripped != profile_name:
        raise ValueError(
            f"Profile name cannot have leading or trailing whitespace: '{profile_name}'"
        )

    base = profile_name.split(".")[0].lower()
    if base in _RESERVED_DEVICE_NAMES or profile_name.lower() in _RESERVED_DEVICE_NAMES:
        raise ValueError(f"Profile name '{profile_name}' is a reserved name")

    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", profile_name):
        raise ValueError(f"Profile name '{profile_name}' contains invalid characters")

    # Case-insensitive collision detection against existing profiles
    profiles_dir = get_storage_dir() / "profiles"
    if profiles_dir.exists():
        for existing in profiles_dir.iterdir():
            if (
                existing.is_dir()
                and existing.name.lower() == profile_name.lower()
                and existing.name != profile_name
            ):
                raise ValueError(
                    f"Case-insensitive collision with existing profile '{existing.name}' for '{profile_name}'"
                )


def get_auth_storage_mode(profile_name: str = "default") -> str:
    """Get effective storage mode ('protected' or 'file') for a profile.

    Resolution order:
      1. NLM_AUTH_STORAGE environment variable (process override, invalid fails closed).
      2. Profile's storage-mode.json marker file (missing means file, corrupt fails closed).
      3. Default 'file'.
    """
    validate_profile_name(profile_name, strict=False)

    # 1. Environment override
    if env_mode := os.environ.get("NLM_AUTH_STORAGE"):
        mode = env_mode.strip().lower()
        if mode not in ("protected", "file"):
            raise ValueError(
                f"Invalid NLM_AUTH_STORAGE: '{env_mode}'. Must be 'protected' or 'file'"
            )
        return mode

    # 2. Profile marker
    profile_dir = (get_storage_dir() / "profiles") / profile_name
    marker_path = profile_dir / "storage-mode.json"
    if not marker_path.exists():
        return "file"

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Marker is not a JSON object")
        if data.get("version") != 1:
            raise ValueError(f"Unsupported storage-mode version: {data.get('version')}")
        mode_val = data.get("mode")
        if mode_val not in ("protected", "file"):
            raise ValueError(f"Invalid mode in marker: {mode_val}")
        return str(mode_val)
    except Exception as e:
        raise ValueError(f"Corrupt storage-mode.json in profile '{profile_name}': {e}") from e


def set_auth_storage_mode(profile_name: str, mode: str) -> None:
    """Persist storage mode for a profile in a 0600 storage-mode.json marker."""
    import sys

    mode_clean = mode.strip().lower()
    if mode_clean not in ("protected", "file"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'protected' or 'file'")

    if mode_clean == "protected":
        try:
            validate_profile_name(profile_name, strict=True)
        except ValueError as exc:
            raise ValueError(
                f"Profile name '{profile_name}' contains characters unsupported by protected mode. "
                f"Please rename it first with 'nlm login profile rename \"{profile_name}\" <new_name>'."
            ) from exc
    else:
        validate_profile_name(profile_name, strict=False)

    profile_dir = get_profile_dir(profile_name)
    safe_mkdir(profile_dir, parents=True)
    marker_path = profile_dir / "storage-mode.json"

    content = json.dumps({"version": 1, "mode": mode_clean}, indent=2) + "\n"
    temp_path = profile_dir / f"storage-mode.json.tmp.{os.getpid()}"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    if sys.platform != "win32":
        os.chmod(temp_path, 0o600)
    os.replace(temp_path, marker_path)


# In-process override for "which account to use" (set by the MCP profile tool).
_session_profile: str | None = None


def load_config() -> Config:
    """Load configuration from file and environment."""
    config_file = get_config_file()
    config_data: dict[str, Any] = {}

    # Load from file if exists
    if config_file.exists():
        try:
            import tomllib

            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)
        except Exception as e:
            raise ConfigError(
                f"Corrupt configuration file: {config_file}\n"
                f"Error: {e}\n"
                "To reset: delete the file or run 'nlm config reset'"
            ) from e

    # Apply environment overrides
    if output_format := os.environ.get("NLM_OUTPUT_FORMAT"):
        config_data.setdefault("output", {})["format"] = output_format

    if os.environ.get("NLM_NO_COLOR"):
        config_data.setdefault("output", {})["color"] = False

    if browser := os.environ.get("NLM_BROWSER"):
        config_data.setdefault("auth", {})["browser"] = browser

    if browser_path := os.environ.get("NLM_BROWSER_PATH"):
        config_data.setdefault("auth", {})["browser_path"] = browser_path

    if profile := os.environ.get("NLM_PROFILE"):
        config_data.setdefault("auth", {})["default_profile"] = profile

    if _session_profile:
        config_data.setdefault("auth", {})["default_profile"] = _session_profile

    return Config(**config_data)


def save_config(config: Config) -> None:
    """Save configuration to file using tomlkit, preserving unknown tables and omitting env overlays."""
    import tomlkit

    config_file = get_config_file()
    safe_mkdir(config_file.parent, parents=True)

    doc: Any = tomlkit.document()
    if config_file.exists():
        try:
            doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
        except Exception:
            doc = tomlkit.document()

    # Update output table
    if "output" not in doc:
        doc["output"] = tomlkit.table()
    doc["output"]["format"] = config.output.format
    doc["output"]["color"] = config.output.color
    doc["output"]["short_ids"] = config.output.short_ids

    # Update auth table, avoiding persisting env overlays
    if "auth" not in doc:
        doc["auth"] = tomlkit.table()
    if not os.environ.get("NLM_BROWSER"):
        doc["auth"]["browser"] = config.auth.browser
    if not os.environ.get("NLM_BROWSER_PATH"):
        doc["auth"]["browser_path"] = config.auth.browser_path
    if not os.environ.get("NLM_PROFILE") and not _session_profile:
        doc["auth"]["default_profile"] = config.auth.default_profile

    temp_file = config_file.parent / f"config.toml.tmp.{os.getpid()}"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, config_file)


def _config_to_toml(config: Config) -> str:
    """Convert config model to TOML string."""
    lines = []

    lines.append("[output]")
    lines.append(f'format = "{config.output.format}"')
    lines.append(f"color = {'true' if config.output.color else 'false'}")
    lines.append(f"short_ids = {'true' if config.output.short_ids else 'false'}")
    lines.append("")

    lines.append("[auth]")
    lines.append(f'browser = "{config.auth.browser}"')
    lines.append(f"browser_path = {json.dumps(config.auth.browser_path)}")
    lines.append(f'default_profile = "{config.auth.default_profile}"')
    lines.append("")

    return "\n".join(lines)


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None


def set_session_profile(name: str | None) -> None:
    """Make 'which account to use' lookups in this process use `name` (None clears it)."""
    global _session_profile
    _session_profile = name.strip() if name and name.strip() else None
    reset_config()


def get_session_profile() -> str | None:
    """The in-process profile override set by set_session_profile(), if any."""
    return _session_profile


def get_saved_default_profile() -> str:
    """default_profile as written in config.toml, ignoring session and env overrides."""
    config_file = get_config_file()
    if config_file.exists():
        try:
            import tomllib

            with open(config_file, "rb") as f:
                return str(tomllib.load(f).get("auth", {}).get("default_profile", "default"))
        except Exception:
            pass
    return "default"


def get_base_default_profile() -> str:
    """The default profile ignoring this process's session override (NLM_PROFILE, else saved)."""
    return os.environ.get("NLM_PROFILE") or get_saved_default_profile()
