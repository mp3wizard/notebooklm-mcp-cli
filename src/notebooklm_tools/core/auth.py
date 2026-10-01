"""Authentication helper for NotebookLM MCP CLI.

Uses Chrome DevTools MCP to extract auth tokens from an authenticated browser session.
If the user is not logged in, prompts them to log in via the Chrome window.

Storage location: ~/.notebooklm-mcp-cli/ (unified for CLI and MCP)
"""

import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from notebooklm_tools.utils.config import get_base_url

# Use logging instead of print to avoid corrupting MCP stdio protocol
logger = logging.getLogger(__name__)


@dataclass
class AuthTokens:
    """Authentication tokens for NotebookLM.

    Only cookies are required. CSRF token and session ID are optional because
    they can be auto-extracted from the NotebookLM page when needed.
    """

    cookies: dict[str, str] | list[dict[str, Any]]
    csrf_token: str = ""  # Optional - auto-extracted from page
    session_id: str = ""  # Optional - auto-extracted from page
    build_label: str = ""  # Optional - auto-extracted from page (cfb2h key)
    base_host: str = ""  # Optional - host the browser was signed in on (issue #269)
    extracted_at: float = 0.0
    revision: str | None = None

    def to_dict(self) -> dict:
        return {
            "cookies": self.cookies,
            "csrf_token": self.csrf_token,
            "session_id": self.session_id,
            "build_label": self.build_label,
            "base_host": self.base_host,
            "extracted_at": self.extracted_at,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthTokens":
        return cls(
            cookies=data["cookies"],
            csrf_token=data.get("csrf_token", ""),
            session_id=data.get("session_id", ""),
            build_label=data.get("build_label", ""),
            base_host=data.get("base_host", ""),
            extracted_at=data.get("extracted_at", 0),
            revision=data.get("revision"),
        )

    def is_expired(self, max_age_hours: float = 168) -> bool:
        """Check if cookies are older than max_age_hours.

        Default is 168 hours (1 week) since cookies are stable for weeks.
        The CSRF token/session ID will be auto-refreshed regardless.
        """
        age_seconds = time.time() - self.extracted_at
        return age_seconds > (max_age_hours * 3600)

    @property
    def cookie_header(self) -> str:
        """Get cookies as a header string."""
        cookies = _flatten_cookie_input(self.cookies)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())


def get_cache_path() -> Path:
    """Get the path to the auth cache file.

    Uses ~/.notebooklm-mcp-cli/auth.json (unified location).
    """
    from notebooklm_tools.utils.config import get_auth_cache_file

    return get_auth_cache_file()


def ensure_profile_ready(profile_name: str | None = None) -> None:
    """Ensure profile is ready for authentication operations.

    Validates profile name and reconciles pending operation markers.
    """
    from notebooklm_tools.core.auth_migration import reconcile_pending_operations
    from notebooklm_tools.utils.config import get_config, validate_profile_name

    target_profile = (profile_name or get_config().auth.default_profile).strip()
    validate_profile_name(target_profile, strict=False)
    reconcile_pending_operations(target_profile)


def load_cached_tokens(profile_name: str | None = None) -> AuthTokens | None:
    """Load tokens from a profile, with legacy fallback for the default only.

    Note: We no longer reject tokens based on age. The functional check
    (redirect to login during CSRF refresh) is the real validity test.
    Cookies often last much longer than any arbitrary time limit.
    """
    ensure_profile_ready(profile_name)

    # 1. Try the requested profile first (Unified Auth)
    manager = get_auth_manager(profile_name)
    if manager.profile_exists():
        try:
            profile = manager.load_profile()
            return AuthTokens(
                cookies=profile.cookies,
                csrf_token=profile.csrf_token or "",
                session_id=profile.session_id or "",
                build_label=profile.build_label or "",
                base_host=profile.base_host or "",
                extracted_at=(
                    profile.last_validated.timestamp() if profile.last_validated else time.time()
                ),
                revision=getattr(profile, "revision", None),
            )
        except Exception as e:
            from notebooklm_tools.utils.config import get_auth_storage_mode

            if get_auth_storage_mode(manager.profile_name) == "protected":
                # Protected mode must NEVER silently swallow store errors into stale root auth.json!
                raise
            logger.debug(f"Failed to load auth profile: {e}")

    # A named non-default profile must never inherit credentials from the
    # single-account legacy cache.
    if profile_name is not None:
        from notebooklm_tools.utils.config import get_config

        if profile_name != get_config().auth.default_profile:
            return None

    # 2. Fallback to legacy auth cache (with auto-migration) for default profile only
    cache_path = get_cache_path()

    # Auto-migrate from old location if needed
    if not cache_path.exists():
        from notebooklm_tools.utils.config import auto_migrate_if_needed

        auto_migrate_if_needed()

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        tokens = AuthTokens.from_dict(data)

        # Just warn if tokens are old, but still return them
        # Let the API client's functional check determine validity
        if tokens.is_expired():
            logger.warning("Cached tokens are older than 1 week. They may still work.")

        return tokens
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to load cached tokens: {e}")
        return None


def _atomic_write_json(target_path: Path, data: Any) -> None:
    """Write JSON data to a target path atomically with 0600 permissions."""
    import secrets
    import stat

    parent = target_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    # SEC-002: Restrict the parent directory to owner-only access
    parent.chmod(stat.S_IRWXU)  # 0o700
    tmp_path = parent / f"{target_path.name}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(fd)
            raise
        os.replace(tmp_path, target_path)
    finally:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def save_tokens_to_cache(
    tokens: AuthTokens,
    silent: bool = False,
    profile_name: str | None = None,
    expected_revision: str | None = None,
    force: bool = True,
) -> str | None:
    """Save tokens to a profile and mirror the configured default to auth.json in file mode.

    Takes the profile lock first to serialize with concurrent migrations or saves.
    Writes root mirror only for file-mode configured default profile.
    Propagates all errors without swallowing.
    """
    from notebooklm_tools.core.auth_migration import get_raw_on_disk_storage_mode
    from notebooklm_tools.core.credential_store import get_profile_lock
    from notebooklm_tools.utils.config import get_config, get_profile_dir

    default_profile = get_config().auth.default_profile
    target_profile = profile_name or default_profile

    with get_profile_lock(target_profile):
        disk_mode = get_raw_on_disk_storage_mode(target_profile)
        if expected_revision is not None:
            from notebooklm_tools.core.credential_store import (
                StaleRevisionError,
                get_envelope_revision,
            )

            if disk_mode == "protected":
                enc_path = get_profile_dir(target_profile, create=False) / "credentials.enc"
                current_rev = get_envelope_revision(enc_path) if enc_path.exists() else None
                if current_rev != expected_revision:
                    raise StaleRevisionError(target_profile, expected_revision, current_rev)
            else:
                raise StaleRevisionError(target_profile, expected_revision, None)

        if disk_mode == "file" and target_profile == default_profile:
            root_cache = get_cache_path()
            root_data = {
                "cookies": tokens.cookies,
                "csrf_token": tokens.csrf_token or "",
                "session_id": tokens.session_id or "",
                "build_label": tokens.build_label or "",
                "base_host": tokens.base_host or "",
                "email": "",
            }
            meta_path = get_profile_dir(target_profile, create=False) / "metadata.json"
            if meta_path.exists():
                with contextlib.suppress(Exception):
                    m = json.loads(meta_path.read_text(encoding="utf-8"))
                    if isinstance(m, dict) and m.get("email"):
                        root_data["email"] = m["email"]
            _atomic_write_json(root_cache, root_data)

        manager = get_auth_manager(target_profile)
        saved_profile = manager.save_profile(
            cookies=tokens.cookies,
            csrf_token=tokens.csrf_token or None,
            session_id=tokens.session_id or None,
            build_label=tokens.build_label or None,
            base_host=tokens.base_host or None,
            force=force,
            expected_revision=expected_revision,
        )

    if not silent:
        logger.info(f"Auth tokens cached for profile '{target_profile}'")
    return getattr(saved_profile, "revision", None)


def extract_tokens_via_chrome_devtools() -> AuthTokens | None:
    """
    Extract auth tokens using Chrome DevTools.

    This function assumes Chrome DevTools MCP is available and connected
    to a Chrome browser. It will:
    1. Navigate to notebooklm.google.com
    2. Check if logged in
    3. If not, wait for user to log in
    4. Extract cookies and CSRF token

    Returns:
        AuthTokens if successful, None otherwise
    """
    # This is a placeholder - the actual implementation would use
    # Chrome DevTools MCP tools. Since we're inside an MCP server,
    # we can't directly call another MCP's tools.
    #
    # Instead, we'll provide a CLI command that can be run separately
    # to extract and cache the tokens.

    raise NotImplementedError(
        "Direct Chrome DevTools extraction not implemented. "
        "Use the 'nlm login' CLI command instead."
    )


def extract_csrf_from_page_source(html: str) -> str | None:
    """Extract CSRF token from page HTML.

    The token is stored in WIZ_global_data.SNlM0e or similar structures.
    """
    import re

    # Try different patterns for CSRF token
    patterns = [
        r'"SNlM0e":"([^"]+)"',  # WIZ_global_data.SNlM0e
        r'at=([^&"]+)',  # Direct at= value
        r'"FdrFJe":"([^"]+)"',  # Alternative location
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    return None


def extract_session_id_from_page(html: str) -> str | None:
    """Extract session ID from page HTML."""
    import re

    patterns = [
        r'"FdrFJe":"([^"]+)"',
        r"f\.sid=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    return None


# ============================================================================
# CLI Authentication Flow
# ============================================================================
#
# This is designed to be run as a separate command before starting the MCP.
# It uses Chrome DevTools MCP interactively to extract auth tokens.
#
# Usage:
#   1. Make sure Chrome is open with DevTools MCP connected
#   2. Run: nlm login
#   3. If not logged in, log in via the Chrome window
#   4. Tokens are cached to ~/.notebooklm-mcp-cli/auth.json
#   5. Start the MCP server - it will use cached tokens
#
# The auth flow script is separate because:
# - MCP servers can't easily call other MCP tools
# - Interactive login needs user attention
# - Caching allows the MCP to start without browser interaction


def parse_cookies_from_chrome_format(cookies_list: list[dict]) -> dict[str, str]:
    """Parse cookies from Chrome DevTools format to simple dict."""
    result = {}
    for cookie in cookies_list:
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if name:
            result[name] = value
    return result


# Tokens that need to be present for auth to work
REQUIRED_COOKIES = ["SID", "HSID", "SSID", "APISID", "SAPISID"]


def _flatten_cookie_input(cookies: dict[str, str] | list[dict[str, Any]]) -> dict[str, str]:
    """Flatten cookies while preferring exact ``.google.com`` domain values."""
    from notebooklm_tools.utils.browser import flatten_cookies

    return flatten_cookies(cookies)


def validate_cookies(cookies: dict[str, str] | list[dict[str, Any]]) -> bool:
    """Check if required cookies are present."""
    flat = _flatten_cookie_input(cookies)
    return all(required in flat for required in REQUIRED_COOKIES)


# =============================================================================
# Multi-Profile Authentication (for CLI)
# =============================================================================


class Profile:
    """Represents an authentication profile (for CLI multi-account support)."""

    def __init__(
        self,
        name: str,
        cookies: list[dict] | dict[str, str],
        csrf_token: str | None = None,
        session_id: str | None = None,
        email: str | None = None,
        last_validated: Any = None,
        build_label: str | None = None,
        base_host: str | None = None,
        browser_backend: str | None = None,
        revision: str | None = None,
    ) -> None:
        self.name = name
        self.cookies = cookies
        self.csrf_token = csrf_token
        self.session_id = session_id
        self.email = email
        self.last_validated = last_validated
        self.build_label = build_label
        self.base_host = base_host
        self.browser_backend = browser_backend
        self.revision = revision

    def to_dict(self) -> dict:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "cookies": self.cookies,
            "csrf_token": self.csrf_token,
            "session_id": self.session_id,
            "email": self.email,
            "build_label": self.build_label,
            "base_host": self.base_host,
            "browser_backend": self.browser_backend,
            "last_validated": (self.last_validated.isoformat() if self.last_validated else None),
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        """Create profile from dictionary."""
        from datetime import datetime

        last_validated = None
        if data.get("last_validated"):
            with contextlib.suppress(ValueError, TypeError):
                last_validated = datetime.fromisoformat(data["last_validated"])

        return cls(
            name=data.get("name", "default"),
            cookies=(
                data.get("cookies", [])
                if isinstance(data.get("cookies"), list)
                else data.get("cookies", {})
            ),
            csrf_token=data.get("csrf_token"),
            session_id=data.get("session_id"),
            email=data.get("email"),
            last_validated=last_validated,
            build_label=data.get("build_label"),
            base_host=data.get("base_host"),
            browser_backend=data.get("browser_backend"),
            revision=data.get("revision"),
        )


class AuthManager:
    """Manages authentication profiles and credentials (for CLI multi-account support)."""

    def __init__(self, profile_name: str = "default") -> None:
        self.profile_name = profile_name
        self._profile: Profile | None = None

    @property
    def profile_dir(self) -> Path:
        """Get the directory for the current profile."""
        from notebooklm_tools.utils.config import get_profile_dir

        return get_profile_dir(self.profile_name)

    @property
    def cookies_file(self) -> Path:
        """Get the cookies file path."""
        return self.profile_dir / "cookies.json"

    @property
    def metadata_file(self) -> Path:
        """Get the metadata file path."""
        return self.profile_dir / "metadata.json"

    def profile_exists(self) -> bool:
        """Check if the profile exists with saved credentials.

        Avoids creating profile directories merely to check credential existence.
        A mode-only marker (storage-mode.json) alone does not make profile_exists True.
        """
        from notebooklm_tools.utils.config import get_profile_dir

        try:
            profile_path = get_profile_dir(self.profile_name, create=False)
        except TypeError:
            profile_path = get_profile_dir(self.profile_name)

        if not profile_path.exists():
            return False
        return (
            (profile_path / "cookies.json").exists()
            or (profile_path / "auth.json").exists()
            or (profile_path / "credentials.enc").exists()
        )

    def load_profile(self, force_reload: bool = False) -> Profile:
        """Load the current profile from disk."""
        from datetime import datetime

        from notebooklm_tools.core.credential_store import CredentialStore
        from notebooklm_tools.core.exceptions import (
            AuthenticationError,
            ProfileNotFoundError,
        )
        from notebooklm_tools.utils.config import get_auth_storage_mode

        if self._profile is not None and not force_reload:
            return self._profile

        if not self.profile_exists():
            raise ProfileNotFoundError(self.profile_name)

        mode = get_auth_storage_mode(self.profile_name)

        if mode == "protected":
            # If plain cookies.json also exists in protected mode, check for conflict
            if self.cookies_file.exists():
                from notebooklm_tools.core.auth_migration import (
                    StorageConflictError,
                    canonical_secrets_equal,
                    capture_file_mode_snapshot,
                    capture_protected_snapshot,
                )

                snap_file = capture_file_mode_snapshot(self.profile_name)
                snap_prot = capture_protected_snapshot(self.profile_name)
                if snap_file and snap_prot and not canonical_secrets_equal(snap_file, snap_prot):
                    raise StorageConflictError(self.profile_name)

            metadata: dict[str, Any] = {}
            if self.metadata_file.exists():
                with contextlib.suppress(Exception):
                    metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))

            store = CredentialStore()
            # If read_credentials raises a store error (e.g. BackendUnavailableError, MissingKeyError),
            # let it propagate so callers distinguish missing key, locked backend, corrupt ciphertext.
            payload = store.read_credentials(self.profile_name)
            if payload is None:
                raise ProfileNotFoundError(self.profile_name)

            from notebooklm_tools.core.credential_store import get_envelope_revision

            enc_path = self.profile_dir / "credentials.enc"
            rev = get_envelope_revision(enc_path) if enc_path.exists() else None

            self._profile = Profile(
                name=self.profile_name,
                cookies=payload["cookies"],
                csrf_token=payload.get("csrf_token"),
                session_id=payload.get("session_id"),
                email=metadata.get("email"),
                last_validated=(
                    datetime.fromisoformat(metadata["last_validated"])
                    if metadata.get("last_validated")
                    else None
                ),
                build_label=metadata.get("build_label"),
                base_host=metadata.get("base_host"),
                browser_backend=metadata.get("browser_backend"),
                revision=rev,
            )
            return self._profile

        # File mode: load legacy plaintext files
        try:
            cookies = json.loads(self.cookies_file.read_text(encoding="utf-8"))
            metadata = {}
            if self.metadata_file.exists():
                metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))

            self._profile = Profile(
                name=self.profile_name,
                cookies=cookies,
                csrf_token=metadata.get("csrf_token"),
                session_id=metadata.get("session_id"),
                email=metadata.get("email"),
                last_validated=(
                    datetime.fromisoformat(metadata["last_validated"])
                    if metadata.get("last_validated")
                    else None
                ),
                build_label=metadata.get("build_label"),
                base_host=metadata.get("base_host"),
                browser_backend=metadata.get("browser_backend"),
            )
            return self._profile
        except Exception as e:
            raise AuthenticationError(
                message=f"Failed to load profile '{self.profile_name}': {e}",
                hint="The profile may be corrupted. Try 'nlm login' to re-authenticate.",
            ) from e

    def save_profile(
        self,
        cookies: list[dict] | dict[str, str],
        csrf_token: str | None = None,
        session_id: str | None = None,
        email: str | None = None,
        force: bool = False,
        build_label: str | None = None,
        base_host: str | None = None,
        browser_backend: str | None = None,
        expected_revision: str | None = None,
    ) -> Profile:
        """Save credentials to the current profile.

        Raises:
            AccountMismatchError: If the profile already has credentials for a
                different email and force is False.
        """
        from datetime import datetime

        from notebooklm_tools.core.auth_migration import get_raw_on_disk_storage_mode
        from notebooklm_tools.core.credential_store import (
            CredentialStore,
            StaleRevisionError,
            get_envelope_revision,
            get_profile_lock,
        )
        from notebooklm_tools.core.exceptions import AccountMismatchError, AuthenticationError
        from notebooklm_tools.utils.config import safe_mkdir

        with get_profile_lock(self.profile_name):
            # Guard: check for account mismatch before overwriting
            if not force and email and self.metadata_file.exists():
                try:
                    existing_metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                    stored_email = existing_metadata.get("email")
                    if stored_email and stored_email != email:
                        raise AccountMismatchError(
                            stored_email=stored_email,
                            new_email=email,
                            profile_name=self.profile_name,
                        )
                except (json.JSONDecodeError, KeyError):
                    pass  # Corrupted metadata, allow overwrite

            if not force and browser_backend == "firefox_profile" and self.profile_exists():
                raise AuthenticationError(
                    message="Firefox login cannot verify the Google account for an existing profile",
                    hint="Confirm the account, then run 'nlm login --force' to replace the saved credentials.",
                )

            safe_mkdir(self.profile_dir, parents=True)
            if os.name == "posix":
                self.profile_dir.chmod(0o700)

            preserved_metadata: dict[str, Any] = {}
            if self.metadata_file.exists():
                with contextlib.suppress(Exception):
                    preserved_metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))

            if email is None:
                email = preserved_metadata.get("email")
            if browser_backend is None:
                browser_backend = preserved_metadata.get("browser_backend")

            # Check raw mode strictly UNDER THE LOCK
            mode = get_raw_on_disk_storage_mode(self.profile_name)

            if mode == "protected":
                # Strip secrets from preserved metadata
                preserved_metadata.pop("csrf_token", None)
                preserved_metadata.pop("session_id", None)

                enc_path = self.profile_dir / "credentials.enc"
                current_revision = get_envelope_revision(enc_path) if enc_path.exists() else None
                if expected_revision is not None and current_revision != expected_revision:
                    raise StaleRevisionError(self.profile_name, expected_revision, current_revision)

                store = CredentialStore()

                # Metadata-only check: if credentials.enc already exists and secrets match exactly,
                # do not rewrite credentials.enc or bump its revision
                should_write_ciphertext = True
                if enc_path.exists():
                    try:
                        existing_payload = store.read_credentials(self.profile_name)
                        if (
                            existing_payload is not None
                            and existing_payload.get("cookies") == cookies
                            and (existing_payload.get("csrf_token") or "") == (csrf_token or "")
                            and (existing_payload.get("session_id") or "") == (session_id or "")
                        ):
                            should_write_ciphertext = False
                    except Exception:
                        should_write_ciphertext = True

                if should_write_ciphertext:
                    secret_payload = {
                        "cookies": cookies,
                        "csrf_token": csrf_token or "",
                        "session_id": session_id or "",
                    }
                    store.write_credentials(self.profile_name, secret_payload)

                # In protected mode, metadata.json contains ONLY nonsecret fields
                metadata = {
                    "email": email,
                    "build_label": build_label,
                    "base_host": base_host,
                    "browser_backend": browser_backend,
                    "last_validated": datetime.now().isoformat(),
                }
                _atomic_write_json(self.metadata_file, metadata)

                # Ensure no plain cookie files exist in protected profile
                if self.cookies_file.exists():
                    with contextlib.suppress(OSError):
                        self.cookies_file.unlink()
                legacy_auth = self.profile_dir / "auth.json"
                if legacy_auth.exists():
                    with contextlib.suppress(OSError):
                        legacy_auth.unlink()

                final_revision = get_envelope_revision(enc_path) if enc_path.exists() else None
            else:
                if expected_revision is not None:
                    # Mode switched from protected to file; expected revision does not exist
                    raise StaleRevisionError(self.profile_name, expected_revision, None)

                _atomic_write_json(self.cookies_file, cookies)

                metadata = {
                    "csrf_token": csrf_token,
                    "session_id": session_id,
                    "email": email,
                    "build_label": build_label,
                    "base_host": base_host,
                    "browser_backend": browser_backend,
                    "last_validated": datetime.now().isoformat(),
                }
                _atomic_write_json(self.metadata_file, metadata)

                # Tighten pre-existing files to 0600 on POSIX
                if os.name == "posix":
                    for p in (
                        self.cookies_file,
                        self.metadata_file,
                        self.profile_dir / "auth.json",
                    ):
                        if p.exists():
                            with contextlib.suppress(OSError):
                                p.chmod(0o600)

                final_revision = None

        self._profile = Profile(
            name=self.profile_name,
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
            email=email,
            last_validated=datetime.now(),
            build_label=build_label,
            base_host=base_host,
            browser_backend=browser_backend,
            revision=final_revision,
        )
        return self._profile

    def update_metadata(
        self,
        email: str | None = None,
        build_label: str | None = None,
        base_host: str | None = None,
        browser_backend: str | None = None,
        last_validated: Any = None,
    ) -> None:
        """Update nonsecret metadata on disk without modifying credentials.enc or bumping revision."""
        from datetime import datetime

        from notebooklm_tools.utils.config import get_auth_storage_mode

        if not self.metadata_file.exists():
            return

        try:
            metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

        if get_auth_storage_mode(self.profile_name) == "protected":
            metadata.pop("csrf_token", None)
            metadata.pop("session_id", None)

        if email is not None:
            metadata["email"] = email
        if build_label is not None:
            metadata["build_label"] = build_label
        if base_host is not None:
            metadata["base_host"] = base_host
        if browser_backend is not None:
            metadata["browser_backend"] = browser_backend
        if last_validated is not None:
            if isinstance(last_validated, datetime):
                metadata["last_validated"] = last_validated.isoformat()
            else:
                metadata["last_validated"] = str(last_validated)

        _atomic_write_json(self.metadata_file, metadata)

    def delete_profile(self) -> None:
        """Delete the current profile."""
        import shutil

        from notebooklm_tools.core.credential_store import CredentialStore
        from notebooklm_tools.utils.config import get_auth_storage_mode, get_profiles_dir

        # Get path directly without auto-creating (profile_dir property auto-creates)
        profile_path = get_profiles_dir() / self.profile_name
        if profile_path.exists():
            mode = get_auth_storage_mode(self.profile_name)
            if mode == "protected" or (profile_path / "credentials.enc").exists():
                try:
                    CredentialStore().delete_credentials(self.profile_name)
                except Exception as exc:
                    logger.debug(
                        f"Error deleting protected credentials for '{self.profile_name}': {exc}"
                    )
                    raise

            shutil.rmtree(profile_path)
        self._profile = None

    def get_cookies(self) -> dict[str, str]:
        """Get cookies for the current profile as simple dict."""
        profile = self.load_profile()
        return _flatten_cookie_input(profile.cookies)

    def get_raw_cookies(self) -> list[dict] | dict[str, str]:
        """Get raw cookies (list or dict)."""
        profile = self.load_profile()
        return profile.cookies

    def get_cookie_header(self) -> str:
        """Get Cookie header value for HTTP requests."""
        from notebooklm_tools.utils.browser import cookies_to_header

        return cookies_to_header(self.get_cookies())

    def get_headers(self) -> dict[str, str]:
        """Get headers for NotebookLM API requests."""
        from notebooklm_tools.utils.browser import cookies_to_header

        profile = self.load_profile()
        # Match the live client (base.py): honor the host the account was last
        # signed in on (issue #269) so Origin/Referer point at the saved host
        # (e.g. notebook.google.com) instead of the default. See issue #332.
        base_url = get_base_url(profile.base_host or None)
        headers = {
            "Cookie": cookies_to_header(_flatten_cookie_input(profile.cookies)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": base_url,
            "Referer": f"{base_url}/",
        }
        if profile.csrf_token:
            headers["X-Goog-Csrf-Token"] = profile.csrf_token
        return headers

    def check_validity(self, *, live: bool = True, timeout: float = 12.0) -> "AuthCheckResult":
        """Check the validity of the current profile's credentials."""
        return check_auth(profile=self.profile_name, live=live, timeout=timeout)

    @staticmethod
    def list_profiles() -> list[str]:
        """List all available profiles."""
        from notebooklm_tools.utils.config import get_profiles_dir

        profiles_dir = get_profiles_dir()
        if not profiles_dir.exists():
            return []
        return [d.name for d in profiles_dir.iterdir() if d.is_dir()]

    def login_with_file(self, file_path: str | Path) -> Profile:
        """Parse cookies from file and save to profile."""
        from urllib.parse import urlparse

        from notebooklm_tools.core.exceptions import AuthenticationError
        from notebooklm_tools.utils.browser import (
            parse_cookies_from_file,
            validate_notebooklm_cookies,
        )
        from notebooklm_tools.utils.config import _ALLOWED_BASE_HOSTS

        cookies = parse_cookies_from_file(file_path)

        if not validate_notebooklm_cookies(cookies):
            raise AuthenticationError(
                message="Parsed cookies don't appear to be valid for NotebookLM",
                hint="Make sure the file contains cookies from a NotebookLM session.",
            )

        base_urls = [get_base_url()]
        if not os.environ.get("NOTEBOOKLM_BASE_URL"):
            rebrand_url = "https://notebook.google.com"
            if rebrand_url not in base_urls:
                base_urls.append(rebrand_url)

        responses = 0
        for base_url in base_urls:
            try:
                response = _fetch_notebooklm_homepage(cookies, base_url=base_url)
            except Exception as exc:
                logger.debug("Manual login host probe failed for %s: %s", base_url, exc)
                continue

            responses += 1
            final_host = urlparse(str(response.url)).hostname or ""
            if response.status_code == 200 and final_host in _ALLOWED_BASE_HOSTS:
                return self.save_profile(cookies, base_host=final_host)

        if responses == 0:
            raise AuthenticationError(
                message="Could not reach Gemini Notebook to verify imported cookies",
                hint="Check your network connection and NOTEBOOKLM_BASE_URL, then try again.",
            )

        raise AuthenticationError(
            message="Imported cookies were rejected by Gemini Notebook",
            hint="Export fresh cookies from an authenticated Gemini Notebook session and try again.",
        )


def get_auth_manager(profile: str | None = None) -> AuthManager:
    """Get an AuthManager for the specified or default profile."""
    from notebooklm_tools.utils.config import get_config

    if profile is None:
        profile = get_config().auth.default_profile

    return AuthManager(profile)


# =============================================================================
# Elegant Unified Auth Validity Check (the single source of truth)
# =============================================================================


@dataclass
class AuthCheckResult:
    """Result of an authentication validity check.

    This is the canonical return type for all "am I still logged in?"
    questions in the system (CLI --check, MCP server_info, doctor, etc.).
    """

    valid: bool
    reason: str | None = None  # "no_tokens", "expired", "network_error", etc.
    checked_at: float = field(default_factory=time.time)
    live: bool = True
    profile: str = "default"
    details: dict[str, Any] | None = None  # e.g. extracted csrf on success


# Browser-like headers required for the NotebookLM homepage fetch.
# These match _PAGE_FETCH_HEADERS in BaseClient (core/base.py).
# The Sec-Fetch-* headers are critical: without them Google may redirect
# even valid cookies to the login page, causing false "expired" results.
_PAGE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def _fetch_notebooklm_homepage(
    cookies: dict[str, str] | list[dict],
    *,
    timeout: float = 12.0,
    base_url: str | None = None,
):
    """Minimal, isolated homepage fetch used for the live auth check.

    Returns the final response after redirects. Callers decide what the
    final URL / status means.

    Note: uses proper browser-like _PAGE_FETCH_HEADERS (including Sec-Fetch-*)
    to avoid false redirects to Google login that occur with minimal headers.
    """
    import httpx

    from notebooklm_tools.utils.browser import cookies_to_header

    cookie_dict = _flatten_cookie_input(cookies)

    headers = _PAGE_FETCH_HEADERS.copy()

    cookie_header = cookies_to_header(cookie_dict)
    if cookie_header:
        headers["Cookie"] = cookie_header

    url = base_url or get_base_url()
    from notebooklm_tools.utils.config import get_enterprise_location, get_enterprise_project_id

    loc = get_enterprise_location()
    prefix = ""
    if "vertexaisearch.cloud.google.com" in url:
        prefix = f"/notebooklm/{loc}"
    elif "cloud.google.com" in url:
        prefix = f"/{loc}"

    project_id = get_enterprise_project_id()
    project_query = f"?project={quote(project_id, safe='')}" if project_id and prefix else ""

    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        return client.get(f"{url}{prefix}/{project_query}")


def check_auth(
    profile: str | None = None,
    *,
    live: bool = True,
    timeout: float = 12.0,
) -> AuthCheckResult:
    """Single source of truth for whether NotebookLM credentials are valid.

    This is the elegant root fix for the long-standing inconsistency between
    `nlm login --check` (live) and `server_info` (pure heuristic).

    live=True  → performs the authoritative minimal network check (homepage
                 fetch + Google login redirect detection). This is what
                 users and the MCP should trust.
    live=False → fast path based only on on-disk metadata (last_validated /
                 extracted_at). Useful for very hot paths.

    Returns an AuthCheckResult that both CLI and MCP code can render.
    """
    if profile is None:
        from notebooklm_tools.utils.config import get_config

        profile = get_config().auth.default_profile

    manager = AuthManager(profile)

    # Fast path: no profile at all
    if not manager.profile_exists():
        return AuthCheckResult(
            valid=False,
            reason="no_tokens",
            live=live,
            profile=profile,
        )

    try:
        p = manager.load_profile()
    except Exception as e:
        return AuthCheckResult(
            valid=False,
            reason=f"load_error: {e}",
            live=live,
            profile=profile,
        )

    # Convert to simple dict for the fetch helper.
    cookie_dict = _flatten_cookie_input(p.cookies)

    if not cookie_dict:
        return AuthCheckResult(valid=False, reason="no_tokens", live=live, profile=profile)

    if not live:
        # Pure heuristic based on last successful validation
        if p.last_validated:
            # Consider anything validated in the last 7 days as good for the
            # non-live path (same spirit as the old 168h rule).
            age = (time.time() - p.last_validated.timestamp()) / 3600
            if age <= 168:
                return AuthCheckResult(
                    valid=True,
                    live=False,
                    profile=profile,
                    checked_at=p.last_validated.timestamp(),
                )
        return AuthCheckResult(valid=False, reason="stale_heuristic", live=False, profile=profile)

    # === Live authoritative path ===
    try:
        resp = _fetch_notebooklm_homepage(cookie_dict, timeout=timeout)

        final_url = str(resp.url)
        redirected_to_login = "accounts.google.com" in final_url

        if not redirected_to_login and resp.status_code == 200:
            # Clean authenticated homepage: fast positive. Extract fresh CSRF
            # while we're here and record last_validated.
            csrf = extract_csrf_from_page_source(resp.text) or ""
            manager.save_profile(
                cookies=p.cookies,
                csrf_token=csrf or p.csrf_token,
                session_id=p.session_id,
                email=p.email,
                build_label=p.build_label,
                base_host=p.base_host,
            )
            return AuthCheckResult(
                valid=True,
                reason=None,
                live=True,
                profile=profile,
                details={"csrf_token": csrf} if csrf else None,
            )

        if not redirected_to_login:
            return AuthCheckResult(
                valid=False,
                reason=f"http_{resp.status_code}",
                live=True,
                profile=profile,
            )

        # A homepage login redirect is not definitive. Some live sessions still
        # bounce there, while the batchexecute API accepts the same cookies.

    except Exception as exc:
        # Network / timeout / etc. — be conservative but do not lie.
        # We still have the cookies on disk; caller can decide.
        return AuthCheckResult(
            valid=False,
            reason=f"network_error: {type(exc).__name__}",
            live=True,
            profile=profile,
            details={"exception": str(exc)},
        )

    # Homepage bounced to login. Confirm with the RPC path real operations use
    # before declaring the profile expired.
    try:
        from notebooklm_tools.core.client import NotebookLMClient
        from notebooklm_tools.core.errors import ClientAuthenticationError
        from notebooklm_tools.core.exceptions import AuthenticationError

        client = NotebookLMClient(
            cookies=p.cookies,
            csrf_token=p.csrf_token or "",
            session_id=p.session_id or "",
            build_label=p.build_label or "",
            base_host=p.base_host or "",
            profile_name=profile,
        )
        try:
            client.list_notebooks()
            refreshed_csrf = client.csrf_token
            refreshed_session = client._session_id
            refreshed_bl = client._bl
        finally:
            client.close()
    except (AuthenticationError, ClientAuthenticationError):
        return AuthCheckResult(
            valid=False,
            reason="expired",
            live=True,
            profile=profile,
            details={"final_url": final_url},
        )
    except Exception as exc:
        return AuthCheckResult(
            valid=False,
            reason=f"network_error: {type(exc).__name__}",
            live=True,
            profile=profile,
            details={"exception": str(exc)},
        )

    manager.save_profile(
        cookies=p.cookies,
        csrf_token=refreshed_csrf or p.csrf_token,
        session_id=refreshed_session or p.session_id,
        email=p.email,
        build_label=refreshed_bl or p.build_label,
        base_host=p.base_host,
    )
    return AuthCheckResult(
        valid=True,
        reason=None,
        live=True,
        profile=profile,
        details={"recovered_via": "rpc"},
    )


# Note: AuthHealthChecker, AuthProbeResult, AuthHealthReport live in
# notebooklm_tools.services.auth — they are business logic (multi-probe
# orchestration, caching, verdict aggregation) and belong in the services
# layer, not here. The thin re-export shim in services.auth makes them
# available to cli/ and mcp/ without breaking the layering rule.
