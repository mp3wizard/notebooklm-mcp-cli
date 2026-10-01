"""Operating system credential store integration for Protected mode.

Manages OS-backed encryption keys and AES-256-GCM encrypted credential files.
Provides isolated in-process backends and fail-closed guards for tests.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import json
import os
import secrets
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from keyring.backend import KeyringBackend

if TYPE_CHECKING:
    from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

SERVICE_NAME = "notebooklm-mcp-cli.credentials.v1"
MAX_KEYSTORE_ITEM_LENGTH = 1000
MAX_ENVELOPE_SIZE = 1024 * 1024  # 1 MiB bound
KEY_BYTES = 32  # 256 bits
NONCE_BYTES = 12  # 96 bits for AES-GCM
CURRENT_ENVELOPE_VERSION = 1
LOCK_TIMEOUT_SECONDS = 60.0


class CredentialStoreError(Exception):
    """Base error for credential store operations."""


class RealCredentialStoreAccessAttemptedError(CredentialStoreError):
    """Raised when an unapproved test attempts to access the real OS keystore."""


class KeystoreItemTooLargeError(CredentialStoreError):
    """Raised when an item to store in the OS keystore exceeds the size limit."""


class BackendUnavailableError(CredentialStoreError):
    """Raised when the OS credential store backend is unavailable or locked."""


class BackendMismatchError(BackendUnavailableError):
    """Raised when the OS credential store backend changes after initialization."""


class MissingKeyError(CredentialStoreError):
    """Raised when a profile's encryption key is missing from the OS keystore."""


class InvalidInstallationError(CredentialStoreError):
    """Raised when installation path or identity check fails."""


class InstallationPathMismatchError(InvalidInstallationError):
    """Raised when installation canonical root path does not match current root."""


class CorruptCiphertextError(CredentialStoreError):
    """Raised when ciphertext envelope is corrupt, truncated, or fails authentication."""


class OversizedCiphertextError(CorruptCiphertextError):
    """Raised when ciphertext envelope exceeds the 1 MiB bound."""


class UnsupportedVersionError(CorruptCiphertextError):
    """Raised when ciphertext envelope has an unsupported version."""


class InvalidProfileNameError(CredentialStoreError):
    """Raised when a profile name is invalid for filesystem or keystore use."""


class LockAcquisitionTimeoutError(CredentialStoreError):
    """Raised when acquiring the cross-process profile lock times out."""


class SymlinkPathRejectedError(CredentialStoreError):
    """Raised when a profile directory or credential file is a symlink."""


class StaleRevisionError(CredentialStoreError):
    """Raised when writing credentials fails because the disk revision has changed."""

    def __init__(
        self,
        profile_name: str,
        expected_revision: str | None,
        current_revision: str | None,
    ) -> None:
        self.profile_name = profile_name
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            f"Cannot save credentials for profile '{profile_name}': "
            f"expected revision '{expected_revision}', but current revision is '{current_revision}'. "
            "Credentials were updated concurrently by another process."
        )


def get_envelope_revision(enc_path: Path) -> str | None:
    """Read the unencrypted revision string from an envelope file without locking or decrypting.

    Returns None if the file does not exist, is not readable, is not a dict, or missing 'revision'.
    """
    if not enc_path.exists() or enc_path.is_symlink():
        return None
    try:
        content = enc_path.read_text(encoding="utf-8")
        data = json.loads(content)
        if isinstance(data, dict):
            if data.get("version") != CURRENT_ENVELOPE_VERSION:
                return None
            rev = data.get("revision")
            if isinstance(rev, str) and rev:
                return rev
        return None
    except Exception:
        return None


@dataclass(frozen=True)
class InstallationIdentity:
    """Stable installation identity, canonical root path, and backend identifier."""

    installation_id: str
    canonical_root: str
    backend_id: str = "unknown"


def _read_installation_identity(install_file: Path) -> InstallationIdentity:
    try:
        data = json.loads(install_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise InvalidInstallationError("Corrupt or unreadable installation.json") from exc

    if not isinstance(data, dict):
        raise InvalidInstallationError("installation.json must be a JSON object")

    if data.get("version") != 1:
        raise InvalidInstallationError(
            f"Unsupported installation.json version: {data.get('version')}"
        )

    installation_id = data.get("installation_id")
    canonical_root = data.get("canonical_root")
    backend_id = data.get("backend_id", "unknown")
    if not installation_id or not canonical_root:
        raise InvalidInstallationError("Missing fields in installation.json")

    return InstallationIdentity(
        installation_id=str(installation_id),
        canonical_root=str(canonical_root),
        backend_id=str(backend_id),
    )


def get_installation_identity(
    storage_dir: Path | None = None, worker: CredentialWorkerClient | None = None
) -> InstallationIdentity:
    """Retrieve or generate the stable installation identity."""
    if storage_dir is None:
        from notebooklm_tools.utils.config import get_storage_dir

        storage_dir = get_storage_dir()

    install_file = storage_dir / "installation.json"
    if install_file.exists():
        return _read_installation_identity(install_file)

    from filelock import FileLock

    storage_dir.mkdir(parents=True, exist_ok=True)
    locks_dir = storage_dir / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(locks_dir / "installation.lock", timeout=LOCK_TIMEOUT_SECONDS):
        if install_file.exists():
            return _read_installation_identity(install_file)

        installation_id = secrets.token_hex(16)
        canonical_root = str(storage_dir.resolve())
        backend_id = worker.identify() if worker is not None else get_current_backend_id()

        data = {
            "version": 1,
            "installation_id": installation_id,
            "canonical_root": canonical_root,
            "backend_id": backend_id,
        }

        content = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        try:
            fd = os.open(str(install_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, content)
                os.fsync(fd)
            finally:
                os.close(fd)
        except FileExistsError:
            return _read_installation_identity(install_file)

        return InstallationIdentity(
            installation_id=installation_id,
            canonical_root=canonical_root,
            backend_id=backend_id,
        )


def relocate_installation(storage_dir: Path | None = None) -> InstallationIdentity:
    """Adopt a confirmed moved root by updating canonical_root in installation.json."""
    if storage_dir is None:
        from notebooklm_tools.utils.config import get_storage_dir

        storage_dir = get_storage_dir()

    identity = get_installation_identity(storage_dir)
    canonical_root = str(storage_dir.resolve())

    data = {
        "version": 1,
        "installation_id": identity.installation_id,
        "canonical_root": canonical_root,
        "backend_id": identity.backend_id,
    }

    install_file = storage_dir / "installation.json"
    tmp_file = storage_dir / f"installation.json.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    try:
        content = json.dumps(data, indent=2) + "\n"
        tmp_file.write_text(content, encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, install_file)
    finally:
        if tmp_file.exists():
            with contextlib.suppress(OSError):
                tmp_file.unlink()

    return InstallationIdentity(
        installation_id=identity.installation_id,
        canonical_root=canonical_root,
        backend_id=identity.backend_id,
    )


def check_installation_identity(
    storage_dir: Path | None = None,
    worker: CredentialWorkerClient | None = None,
    expected_backend_id: str | None = None,
) -> InstallationIdentity:
    """Check installation identity and verify canonical root and backend match."""
    if storage_dir is None:
        from notebooklm_tools.utils.config import get_storage_dir

        storage_dir = get_storage_dir()

    identity = get_installation_identity(storage_dir, worker=worker)
    current_root = str(storage_dir.resolve())
    if identity.canonical_root != current_root:
        raise InstallationPathMismatchError(
            f"Installation directory mismatch: canonical root is '{identity.canonical_root}', "
            f"but current root is '{current_root}'. Run 'nlm auth storage relocate' if this was an intentional move."
        )

    # Verify backend identifier if recorded
    if identity.backend_id not in ("unknown", "in_memory", "test_fake"):
        if expected_backend_id is not None:
            current_backend = expected_backend_id
        elif worker is not None:
            current_backend = worker.identify()
        else:
            current_backend = get_current_backend_id()

        if identity.backend_id != current_backend:
            raise BackendMismatchError(
                f"Backend mismatch: installation was initialized with '{identity.backend_id}', "
                f"but current backend is '{current_backend}'. Silent backend switching is prohibited."
            )
    return identity


class CredentialBackend(Protocol):
    """Interface for credential store operations."""

    def get_password(self, service: str, account: str) -> str | None:
        """Retrieve a secret."""
        ...

    def set_password(self, service: str, account: str, password: str) -> None:
        """Store a secret."""
        ...

    def delete_password(self, service: str, account: str) -> None:
        """Delete a secret."""
        ...


class FailClosedCredentialBackend:
    """Backend that raises on any access to prevent accidental OS store usage."""

    def get_password(self, service: str, account: str) -> str | None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Attempted to read from OS credential store (service={service}, account={account}) in test"
        )

    def set_password(self, service: str, account: str, password: str) -> None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Attempted to write to OS credential store (service={service}, account={account}) in test"
        )

    def delete_password(self, service: str, account: str) -> None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Attempted to delete from OS credential store (service={service}, account={account}) in test"
        )


class FailClosedKeyring(KeyringBackend):
    """Keyring backend that fails closed for testing safety."""

    priority = 10

    def get_password(self, service: str, username: str) -> str | None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Direct keyring read attempted (service={service}, username={username}) in test"
        )

    def set_password(self, service: str, username: str, password: str) -> None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Direct keyring write attempted (service={service}, username={username}) in test"
        )

    def delete_password(self, service: str, username: str) -> None:
        raise RealCredentialStoreAccessAttemptedError(
            f"Direct keyring delete attempted (service={service}, username={username}) in test"
        )


class InMemoryCredentialBackend:
    """In-memory credential store backend for isolated tests."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self._store.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        if len(password) > MAX_KEYSTORE_ITEM_LENGTH:
            raise KeystoreItemTooLargeError(
                f"Password length {len(password)} exceeds maximum allowed {MAX_KEYSTORE_ITEM_LENGTH}"
            )
        self._store[(service, account)] = password

    def delete_password(self, service: str, account: str) -> None:
        self._store.pop((service, account), None)
        clear_credential_cache()

    def clear(self) -> None:
        self._store.clear()
        clear_credential_cache()


class KeyringAdapterBackend:
    """Adapts a keyring backend to the CredentialBackend protocol."""

    def __init__(self, keyring_backend: KeyringBackend) -> None:
        self._backend = keyring_backend

    def get_password(self, service: str, account: str) -> str | None:
        return self._backend.get_password(service, account)

    def set_password(self, service: str, account: str, password: str) -> None:
        if len(password) > MAX_KEYSTORE_ITEM_LENGTH:
            raise KeystoreItemTooLargeError(
                f"Item length {len(password)} exceeds maximum keystore limit {MAX_KEYSTORE_ITEM_LENGTH}"
            )
        self._backend.set_password(service, account, password)

    def delete_password(self, service: str, account: str) -> None:
        self._backend.delete_password(service, account)


_backend_factory: Callable[[], CredentialBackend] | None = None


def set_backend_factory(factory: Callable[[], CredentialBackend] | None) -> None:
    """Set the backend factory for credential operations (used for testing)."""
    global _backend_factory
    _backend_factory = factory


def get_backend_factory() -> Callable[[], CredentialBackend] | None:
    """Get the currently configured backend factory."""
    return _backend_factory


def _detect_os_backend() -> tuple[CredentialBackend, str]:
    """Detect and return the platform-specific OS backend and its identifier."""
    # Fail closed during automated tests unless explicitly opted in
    if "PYTEST_CURRENT_TEST" in os.environ and not os.environ.get("ALLOW_REAL_KEYSTORE"):
        raise RealCredentialStoreAccessAttemptedError(
            "Direct OS backend detection attempted in test (_detect_os_backend)"
        )

    if sys.platform == "darwin":
        if "KEYCHAIN_PATH" in os.environ and not os.environ.get("ALLOW_REAL_KEYSTORE"):
            raise BackendUnavailableError(
                "Custom KEYCHAIN_PATH redirection is prohibited in production"
            )
        from keyring.backends import macOS

        backend = macOS.Keyring()  # type: ignore[no-untyped-call]
        backend_id = "macOS.Keyring"
    elif sys.platform == "win32":
        # Note on Windows persistence: WinVaultKeyring stores secrets in the user's
        # Windows Credential Manager via CredWriteW/CredReadW, which persists per user session.
        from keyring.backends import Windows

        backend = Windows.WinVaultKeyring()  # type: ignore[no-untyped-call]
        backend_id = "Windows.WinVaultKeyring"
    else:
        # Linux: Explicitly try supported SecretService, libsecret, KWallet
        backend = None
        backend_id = ""
        try:
            from keyring.backends import SecretService

            ss = SecretService.Keyring()
            if getattr(ss, "priority", 0) > 0:
                backend = ss
                backend_id = "SecretService.Keyring"
        except Exception:
            pass

        if backend is None:
            try:
                from keyring.backends import libsecret

                ls = libsecret.Keyring()
                if getattr(ls, "priority", 0) > 0:
                    backend = ls
                    backend_id = "libsecret.Keyring"
            except Exception:
                pass

        if backend is None:
            try:
                from keyring.backends import KWallet

                kw = KWallet.Keyring()
                if getattr(kw, "priority", 0) > 0:
                    backend = kw
                    backend_id = "KWallet.Keyring"
            except Exception:
                pass

        if backend is None:
            raise BackendUnavailableError(
                "No supported OS credential store found on Linux. SecretService, libsecret, or KWallet is required."
            )

    return KeyringAdapterBackend(backend), backend_id


def get_backend() -> CredentialBackend:
    """Get the active credential backend."""
    if _backend_factory is not None:
        return _backend_factory()
    backend, _ = _detect_os_backend()
    return backend


def get_current_backend_id() -> str:
    """Get the active backend identifier."""
    if _backend_factory is not None:
        active = _backend_factory()
        if isinstance(active, InMemoryCredentialBackend):
            return "in_memory"
        return "test_fake"
    _, backend_id = _detect_os_backend()
    return backend_id


class ProfileLock:
    """Wrapper around FileLock to ensure typed LockAcquisitionTimeoutError on cross-process timeout."""

    def __init__(self, lock: Any, profile_name: str) -> None:
        self._lock = lock
        self._profile_name = profile_name

    def acquire(self, *args: Any, **kwargs: Any) -> Any:
        from filelock import Timeout as FileLockTimeout

        try:
            return self._lock.acquire(*args, **kwargs)
        except FileLockTimeout as exc:
            raise LockAcquisitionTimeoutError(
                f"Cannot acquire profile lock for '{self._profile_name}': "
                "another nlm process is changing this profile's storage; try again."
            ) from exc

    def release(self, *args: Any, **kwargs: Any) -> Any:
        return self._lock.release(*args, **kwargs)

    def __enter__(self) -> ProfileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


_LOCKS_CACHE: dict[Path, Any] = {}
_LOCKS_MUTEX = threading.Lock()


def get_profile_lock(profile_name: str, storage_dir: Path | None = None) -> ProfileLock:
    """Return a shared FileLock instance for the profile within the process.

    Sharing the FileLock instance enables re-entrancy within the same process
    while maintaining OS-level exclusion across processes.
    """
    from filelock import FileLock

    if storage_dir is None:
        from notebooklm_tools.utils.config import get_storage_dir

        storage_dir = get_storage_dir()

    locks_dir = storage_dir / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = (locks_dir / f"{profile_name}.lock").resolve()

    with _LOCKS_MUTEX:
        if lock_path not in _LOCKS_CACHE:
            _LOCKS_CACHE[lock_path] = FileLock(lock_path, timeout=LOCK_TIMEOUT_SECONDS)
        raw_lock = _LOCKS_CACHE[lock_path]
    return ProfileLock(raw_lock, profile_name)


_CREDENTIAL_CACHE: dict[tuple[str, str, str, str], dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()
_IN_FLIGHT_LOADS: dict[tuple[str, str, str, str], tuple[threading.Event, list[Any]]] = {}
_IN_FLIGHT_LOCK = threading.Lock()


def clear_credential_cache() -> None:
    """Clear the in-memory credential cache (for test resets and key deletions)."""
    with _CACHE_LOCK:
        _CREDENTIAL_CACHE.clear()


class CredentialStore:
    """Core credential store for Protected mode.

    Manages per-profile OS-backed encryption keys and AES-256-GCM encrypted
    credentials.enc files.
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        backend: CredentialBackend | None = None,
        worker_client: CredentialWorkerClient | None = None,
        helper_cmd: list[str] | None = None,
        service_name: str | None = None,
    ) -> None:
        if storage_dir is not None:
            self._storage_dir = storage_dir
        else:
            from notebooklm_tools.utils.config import get_storage_dir

            self._storage_dir = get_storage_dir()
        env_service = (
            os.environ.get("NOTEBOOKLM_KEYSTORE_SERVICE_NAME")
            if os.environ.get("ALLOW_REAL_KEYSTORE")
            else None
        )
        self._service_name = service_name or env_service or SERVICE_NAME
        if worker_client is not None:
            self._worker = worker_client
        elif backend is not None:
            from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

            self._worker = CredentialWorkerClient(backend=backend, use_subprocess=False)
        elif get_backend_factory() is not None:
            from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

            self._worker = CredentialWorkerClient(backend=get_backend(), use_subprocess=False)
        else:
            # PRODUCTION: Must run in helper subprocess!
            from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient

            self._worker = CredentialWorkerClient(
                backend=None, use_subprocess=True, helper_cmd=helper_cmd
            )

    def _validate_profile(self, profile_name: str) -> None:
        from notebooklm_tools.utils.config import ConfigError, validate_profile_name

        try:
            validate_profile_name(profile_name, strict=True)
        except (ValueError, ConfigError) as exc:
            raise InvalidProfileNameError(str(exc)) from exc

    def _get_profile_lock(self, profile_name: str) -> Any:
        return get_profile_lock(profile_name, self._storage_dir)

    def _check_symlink(self, path: Path) -> None:
        if path.is_symlink():
            raise SymlinkPathRejectedError(f"Path '{path}' is a symlink, which is prohibited.")

    def _get_profile_dir(self, profile_name: str) -> Path:
        return self._storage_dir / "profiles" / profile_name

    def _get_operation_marker_path(self, profile_name: str) -> Path:
        return self._storage_dir / "operations" / f"{profile_name}.json"

    def _write_operation_marker(
        self,
        profile_name: str,
        operation: str,
        phase: str,
        expected_revision: str | None = None,
    ) -> None:
        marker_file = self._get_operation_marker_path(profile_name)
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            with contextlib.suppress(OSError):
                marker_file.parent.chmod(0o700)
        data = {
            "version": 1,
            "op_id": secrets.token_hex(8),
            "operation": operation,
            "profile": profile_name,
            "phase": phase,
            "expected_revision": expected_revision,
        }
        tmp = marker_file.parent / f"{marker_file.name}.tmp.{os.getpid()}"
        tmp.write_text(json.dumps(data) + "\n", encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        os.replace(tmp, marker_file)

    def _clear_operation_marker(self, profile_name: str) -> None:
        marker_file = self._get_operation_marker_path(profile_name)
        if marker_file.exists():
            with contextlib.suppress(OSError):
                marker_file.unlink()

    def _read_operation_marker(self, profile_name: str) -> dict[str, Any] | None:
        marker_file = self._get_operation_marker_path(profile_name)
        if not marker_file.exists():
            return None
        try:
            data = json.loads(marker_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return None
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if the OS credential backend is available via a fresh real probe (no cache).

        Used by explicit actions: set protected, resolve, refresh preflight, doctor.
        Executes a throwaway write-read-delete probe (__nlm_probe__<random>) under bounded timeout.
        """
        try:
            backend_id = self._worker.identify()
            if not backend_id or backend_id == "unsupported":
                return False
        except Exception:
            return False

        probe_account = f"__nlm_probe__{secrets.token_hex(6)}"
        try:
            return bool(self._worker.probe(self._service_name, probe_account))
        except Exception:
            return False
        finally:
            with contextlib.suppress(Exception):
                self._worker.delete_password(self._service_name, probe_account)

    def should_offer_protection(self, profile_name: str | None = None) -> bool:
        """Determine whether to invite the user to enable Protected mode.

        Used only by invites/notices: CLI line, MCP notice, login prompt, wizard, server_info.
        Order of evaluation:
        1. Cheap session hints (returns False immediately on SSH, container, headless Linux).
        2. If profile specified: already answered or already protected -> returns False.
        3. Cached keystore probe (30-day TTL). If fresh result exists, returns that.
        4. Real probe at most once per install: runs probe once and caches result in notices.json.
        """
        from notebooklm_tools.core.credential_backend_worker import is_definitely_non_desktop
        from notebooklm_tools.core.notices import (
            cache_probe_result,
            get_cached_probe_result,
            get_protect_answer,
        )
        from notebooklm_tools.utils.config import get_auth_storage_mode

        # 1. Cheap session hints
        if is_definitely_non_desktop():
            return False

        # 2. Profile state checks
        if profile_name:
            if get_protect_answer(profile_name, storage_dir=self._storage_dir) is not None:
                return False
            try:
                if get_auth_storage_mode(profile_name) != "file":
                    return False
            except Exception:
                return False

        # 3. Cached probe result (30 days)
        cached = get_cached_probe_result(storage_dir=self._storage_dir)
        if cached is not None:
            return cached

        # 4. Real probe at most once per install
        available = self.is_available()
        cache_probe_result(available, storage_dir=self._storage_dir)
        return available

    def has_key(self, profile_name: str) -> bool:
        """Check if an encryption key exists in the keystore for the given profile."""
        try:
            identity = get_installation_identity(self._storage_dir, worker=self._worker)
            account_id = f"{identity.installation_id}:{profile_name}"
            pwd = self._worker.get_password(self._service_name, account_id)
            return pwd is not None
        except Exception:
            return False

    def read_credentials(self, profile_name: str) -> dict[str, Any] | None:
        """Read and decrypt credentials for a protected profile."""
        self._validate_profile(profile_name)

        # Reads must NOT mutate installation identity; if installation.json doesn't exist, no credentials exist
        install_file = self._storage_dir / "installation.json"
        if not install_file.exists():
            return None

        profile_dir = self._get_profile_dir(profile_name)
        enc_path = profile_dir / "credentials.enc"

        self._check_symlink(profile_dir)
        if enc_path.is_symlink():
            raise SymlinkPathRejectedError(f"Path '{enc_path}' is a symlink, which is prohibited.")

        if not enc_path.exists():
            return None

        # Check operation marker first: pending or interrupted operation must not serve stale cache
        op_marker = self._read_operation_marker(profile_name)
        if op_marker is not None:
            identity = get_installation_identity(self._storage_dir, worker=self._worker)
            return self._read_credentials_locked(profile_name, enc_path, identity)

        # Check in-memory revision cache
        revision = get_envelope_revision(enc_path)
        if revision is not None:
            identity = get_installation_identity(self._storage_dir, worker=self._worker)
            cache_key = (
                str(self._storage_dir.resolve()),
                identity.installation_id,
                profile_name,
                revision,
            )
            with _CACHE_LOCK:
                cached_payload = _CREDENTIAL_CACHE.get(cache_key)
            if cached_payload is not None:
                return copy.deepcopy(cached_payload)

            # Single-flight cold loads: only 1 in-flight decrypt per (profile, revision)
            with _IN_FLIGHT_LOCK:
                if cache_key in _IN_FLIGHT_LOADS:
                    event, result_box = _IN_FLIGHT_LOADS[cache_key]
                    wait = True
                else:
                    event = threading.Event()
                    result_box = []
                    _IN_FLIGHT_LOADS[cache_key] = (event, result_box)
                    wait = False

            if wait:
                event.wait(timeout=LOCK_TIMEOUT_SECONDS)
                if result_box and isinstance(result_box[0], BaseException):
                    raise result_box[0]
                with _CACHE_LOCK:
                    cached_payload = _CREDENTIAL_CACHE.get(cache_key)
                if cached_payload is not None:
                    return copy.deepcopy(cached_payload)

            try:
                payload = self._read_credentials_locked(profile_name, enc_path, identity)
                if payload is not None:
                    with _CACHE_LOCK:
                        _CREDENTIAL_CACHE[cache_key] = copy.deepcopy(payload)
                return payload
            except BaseException as exc:
                if not wait:
                    result_box.append(exc)
                raise
            finally:
                if not wait:
                    with _IN_FLIGHT_LOCK:
                        _IN_FLIGHT_LOADS.pop(cache_key, None)
                    event.set()

        # If revision is None (missing or corrupt envelope), fall through to locked read
        identity = get_installation_identity(self._storage_dir, worker=self._worker)
        return self._read_credentials_locked(profile_name, enc_path, identity)

    def _read_credentials_locked(
        self, profile_name: str, enc_path: Path, identity: InstallationIdentity
    ) -> dict[str, Any] | None:
        """Perform locked decryption of credentials.enc."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from filelock import Timeout as FileLockTimeout

        try:
            with self._get_profile_lock(profile_name):
                file_size = enc_path.stat().st_size
                if file_size > MAX_ENVELOPE_SIZE:
                    raise OversizedCiphertextError(
                        f"Ciphertext envelope exceeds 1 MiB limit ({file_size} bytes)"
                    )

                try:
                    raw_text = enc_path.read_text(encoding="utf-8")
                    envelope = json.loads(raw_text)
                except (json.JSONDecodeError, OSError) as exc:
                    raise CorruptCiphertextError("Envelope is corrupt or not valid JSON") from exc

                if not isinstance(envelope, dict):
                    raise CorruptCiphertextError("Envelope must be a JSON object")

                version = envelope.get("version")
                if version != CURRENT_ENVELOPE_VERSION:
                    raise UnsupportedVersionError(f"Unsupported envelope version: {version}")

                revision = envelope.get("revision")
                nonce_b64 = envelope.get("nonce")
                ciphertext_b64 = envelope.get("ciphertext")

                if not revision or not nonce_b64 or not ciphertext_b64:
                    raise CorruptCiphertextError(
                        "Missing required envelope fields (revision, nonce, ciphertext)"
                    )

                account_id = f"{identity.installation_id}:{profile_name}"

                key_b64 = self._worker.get_password(self._service_name, account_id)
                if key_b64 is None:
                    # Check if a deletion operation was in progress (distinguish deletion intent from corruption)
                    op_marker = self._read_operation_marker(profile_name)
                    if op_marker and op_marker.get("operation") == "delete":
                        if enc_path.exists():
                            with contextlib.suppress(OSError):
                                enc_path.unlink()
                        self._clear_operation_marker(profile_name)
                        return None
                    raise MissingKeyError(
                        f"Encryption key for profile '{profile_name}' is missing from the OS keystore."
                    )

                try:
                    key_bytes = base64.b64decode(key_b64)
                except Exception as exc:
                    raise CorruptCiphertextError("Invalid base64 key in keystore") from exc

                if len(key_bytes) != KEY_BYTES:
                    raise CorruptCiphertextError("Invalid key length in keystore")

                try:
                    nonce = base64.b64decode(nonce_b64)
                    ciphertext = base64.b64decode(ciphertext_b64)
                except Exception as exc:
                    raise CorruptCiphertextError(
                        "Base64 decoding failed for envelope fields"
                    ) from exc

                aad = f"{version}:{revision}:{identity.installation_id}:{profile_name}".encode()
                aesgcm = AESGCM(key_bytes)
                try:
                    decrypted = aesgcm.decrypt(nonce, ciphertext, aad)
                except Exception as exc:
                    raise CorruptCiphertextError(
                        "Ciphertext envelope failed authentication or decryption"
                    ) from exc

                try:
                    payload = json.loads(decrypted.decode("utf-8"))
                except Exception as exc:
                    raise CorruptCiphertextError("Decrypted payload is not valid JSON") from exc

                if not isinstance(payload, dict):
                    raise CorruptCiphertextError("Decrypted payload must be a JSON object")

                return payload
        except FileLockTimeout as exc:
            raise LockAcquisitionTimeoutError(
                f"Timed out acquiring lock for profile '{profile_name}' after {LOCK_TIMEOUT_SECONDS}s"
            ) from exc

    def write_credentials(self, profile_name: str, payload: dict[str, Any]) -> None:
        """Encrypt and atomically store credentials for a protected profile."""
        self._validate_profile(profile_name)
        identity = get_installation_identity(self._storage_dir, worker=self._worker)
        current_root = str(self._storage_dir.resolve())
        if identity.canonical_root != current_root:
            raise InstallationPathMismatchError(
                f"Installation directory mismatch: canonical root is '{identity.canonical_root}', "
                f"but current root is '{current_root}'. Run 'nlm auth storage relocate' if this was an intentional move."
            )
        profile_dir = self._get_profile_dir(profile_name)
        enc_path = profile_dir / "credentials.enc"

        if profile_dir.exists():
            self._check_symlink(profile_dir)
        if enc_path.exists():
            self._check_symlink(enc_path)

        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from filelock import Timeout as FileLockTimeout

        try:
            with self._get_profile_lock(profile_name):
                account_id = f"{identity.installation_id}:{profile_name}"

                # Write operation marker: preparing
                self._write_operation_marker(profile_name, operation="write", phase="preparing")

                candidate_raw_key = secrets.token_bytes(KEY_BYTES)
                candidate_key_b64 = base64.b64encode(candidate_raw_key).decode("ascii")

                # Single helper process call: ensures key and verifies backend ID in 1 execution
                key_b64, created, backend_id = self._worker.ensure_key(
                    self._service_name,
                    account_id,
                    candidate_key=candidate_key_b64,
                    allow_create=not enc_path.exists(),
                )

                if (
                    identity.backend_id not in ("unknown", "in_memory", "test_fake")
                    and get_backend_factory() is None
                    and identity.backend_id != backend_id
                ):
                    raise BackendMismatchError(
                        f"Backend mismatch: installation was initialized with '{identity.backend_id}', "
                        f"but current backend is '{backend_id}'. Silent backend switching is prohibited."
                    )

                if created:
                    raw_key = candidate_raw_key
                else:
                    try:
                        raw_key = base64.b64decode(key_b64)
                    except Exception as exc:
                        raise CorruptCiphertextError("Invalid base64 key in keystore") from exc

                    if len(raw_key) != KEY_BYTES:
                        raise CorruptCiphertextError("Key in keystore is not 32 bytes")

                nonce = secrets.token_bytes(NONCE_BYTES)
                revision = secrets.token_hex(16)
                version = CURRENT_ENVELOPE_VERSION
                aad = f"{version}:{revision}:{identity.installation_id}:{profile_name}".encode()
                payload_bytes = json.dumps(
                    payload, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")

                aesgcm = AESGCM(raw_key)
                ciphertext = aesgcm.encrypt(nonce, payload_bytes, aad)

                envelope = {
                    "version": version,
                    "revision": revision,
                    "nonce": base64.b64encode(nonce).decode("ascii"),
                    "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                }

                # Update marker to committed before file replacement
                self._write_operation_marker(
                    profile_name, operation="write", phase="committed", expected_revision=revision
                )

                profile_dir.mkdir(parents=True, exist_ok=True)
                tmp_file = profile_dir / f"credentials.enc.tmp.{os.getpid()}.{secrets.token_hex(4)}"
                try:
                    content = json.dumps(envelope, indent=2) + "\n"
                    with open(tmp_file, "w", encoding="utf-8") as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())

                    if os.name == "posix":
                        os.chmod(tmp_file, 0o600)

                    os.replace(tmp_file, enc_path)

                    # fsync parent directory where supported
                    try:
                        dir_flags = os.O_RDONLY
                        if hasattr(os, "O_DIRECTORY"):
                            dir_flags |= os.O_DIRECTORY
                        dir_fd = os.open(str(profile_dir), dir_flags)
                        try:
                            os.fsync(dir_fd)
                        finally:
                            os.close(dir_fd)
                    except OSError:
                        pass
                finally:
                    if tmp_file.exists():
                        with contextlib.suppress(OSError):
                            tmp_file.unlink()

                # Clear operation marker upon successful commit
                self._clear_operation_marker(profile_name)

                # Invalidate in-memory revision cache so next read decrypts and verifies store
                clear_credential_cache()
        except FileLockTimeout as exc:
            raise LockAcquisitionTimeoutError(
                f"Timed out acquiring lock for profile '{profile_name}' after {LOCK_TIMEOUT_SECONDS}s"
            ) from exc

    def delete_credentials(self, profile_name: str) -> None:
        """Delete credentials and encryption key for a protected profile."""
        self._validate_profile(profile_name)
        identity = check_installation_identity(self._storage_dir, worker=self._worker)
        profile_dir = self._get_profile_dir(profile_name)
        enc_path = profile_dir / "credentials.enc"

        if profile_dir.exists():
            self._check_symlink(profile_dir)
        if enc_path.exists():
            self._check_symlink(enc_path)

        from filelock import Timeout as FileLockTimeout

        try:
            with self._get_profile_lock(profile_name):
                # Mark key deletion intent before calling delete, distinguishing intent from corruption
                self._write_operation_marker(profile_name, operation="delete", phase="preparing")

                account_id = f"{identity.installation_id}:{profile_name}"
                self._worker.delete_password(self._service_name, account_id)

                if enc_path.exists():
                    enc_path.unlink()

                self._write_operation_marker(profile_name, operation="delete", phase="cleanup")
                self._clear_operation_marker(profile_name)

                # Clear in-memory revision cache for this profile
                with _CACHE_LOCK:
                    to_del = [k for k in _CREDENTIAL_CACHE if k[2] == profile_name]
                    for k in to_del:
                        _CREDENTIAL_CACHE.pop(k, None)
        except FileLockTimeout as exc:
            raise LockAcquisitionTimeoutError(
                f"Timed out acquiring lock for profile '{profile_name}' after {LOCK_TIMEOUT_SECONDS}s"
            ) from exc
