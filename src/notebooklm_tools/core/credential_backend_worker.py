"""Credential backend worker process and bounded execution.

Runs OS credential store operations in a helper process with bounded deadlines
to prevent GUI keychain popups or hung daemons from blocking the CLI or MCP server.
Secrets are passed via private pipes, never argv, env, or temporary files.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, cast

from notebooklm_tools.core.credential_store import (
    MAX_KEYSTORE_ITEM_LENGTH,
    BackendUnavailableError,
    CredentialBackend,
    CredentialStoreError,
    KeystoreItemTooLargeError,
    RealCredentialStoreAccessAttemptedError,
    get_backend,
)

DEFAULT_TIMEOUT_DESKTOP = 60.0
DEFAULT_TIMEOUT_HEADLESS = 10.0


class BackendTimeoutError(CredentialStoreError):
    """Raised when an OS credential store operation times out."""


def is_desktop_session() -> bool:
    """Detect whether the current process is running in a desktop GUI session."""
    if sys.platform == "darwin":
        # macOS has a GUI window server if not running over an SSH session without window server access
        # If SSH_CONNECTION is set and no display session, treat as non-desktop
        return not (os.environ.get("SSH_CONNECTION") and not os.environ.get("DISPLAY"))
    elif sys.platform == "win32":
        # Windows GUI session (SSH key-auth sessions cannot access Credential Manager)
        return not os.environ.get("SSH_CONNECTION")
    else:
        # Linux: check DISPLAY or WAYLAND_DISPLAY
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def is_definitely_non_desktop() -> bool:
    """Check cheap session hints to immediately detect non-desktop environments.

    Returns True if this is an SSH session, a container, or a Linux session
    without a D-Bus session bus. Used to short-circuit awareness notices/invites
    without spawning helpers or attempting keychain access.
    """
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return True
    if sys.platform.startswith("linux") and not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return True
    return bool(
        os.path.exists("/.dockerenv")
        or os.path.exists("/run/.containerenv")
        or ("container" in os.environ)
        or bool(os.environ.get("CONTAINER"))
        or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
    )


def get_default_timeout() -> float:
    """Return default timeout based on session type."""
    return DEFAULT_TIMEOUT_DESKTOP if is_desktop_session() else DEFAULT_TIMEOUT_HEADLESS


class CredentialWorkerClient:
    """Client for executing credential store operations with a bounded timeout."""

    def __init__(
        self,
        backend: CredentialBackend | None = None,
        use_subprocess: bool = False,
        timeout_seconds: float | None = None,
        helper_cmd: list[str] | None = None,
    ) -> None:
        self._backend = backend
        self._use_subprocess = use_subprocess
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else get_default_timeout()
        )
        self._helper_cmd = helper_cmd
        self._last_helper_proc: subprocess.Popen[str] | None = None

    def get_password(self, service: str, account: str) -> str | None:
        """Retrieve a secret with a bounded deadline."""
        return cast(
            str | None,
            self._execute({"op": "get", "service": service, "account": account}),
        )

    def set_password(self, service: str, account: str, password: str) -> None:
        """Store a secret with a bounded deadline."""
        if len(password) > MAX_KEYSTORE_ITEM_LENGTH:
            raise KeystoreItemTooLargeError(
                f"Password length {len(password)} exceeds maximum allowed {MAX_KEYSTORE_ITEM_LENGTH}"
            )
        self._execute({"op": "set", "service": service, "account": account, "password": password})

    def delete_password(self, service: str, account: str) -> None:
        """Delete a secret with a bounded deadline."""
        self._execute({"op": "delete", "service": service, "account": account})

    def probe(self, service: str, account: str) -> bool:
        """Run a throwaway write-read-delete probe in the keystore."""
        res = self._execute({"op": "probe", "service": service, "account": account})
        return bool(res)

    def identify(self) -> str:
        """Identify the active OS keystore backend."""
        res = self._execute({"op": "identify"})
        return str(res)

    def ensure_key(
        self,
        service: str,
        account: str,
        candidate_key: str,
        allow_create: bool = True,
    ) -> tuple[str, bool, str]:
        """Ensure an encryption key exists, creating and verifying it if missing and permitted.

        Returns:
            Tuple of (key, created, backend_id)
        """
        res = self._execute(
            {
                "op": "ensure_key",
                "service": service,
                "account": account,
                "candidate_key": candidate_key,
                "allow_create": allow_create,
            }
        )
        return res["key"], res["created"], res["backend_id"]

    def _execute(self, request: dict[str, Any]) -> Any:
        # If an explicit in-memory/in-process backend is provided and subprocess is not requested, execute in-process
        if self._backend is not None and not self._use_subprocess:
            return self._execute_in_process(self._backend, request)

        return self._execute_in_helper(request)

    def _execute_in_process(self, backend: CredentialBackend, request: dict[str, Any]) -> Any:
        import concurrent.futures

        op = request["op"]
        service = request.get("service", "")
        account = request.get("account", "")

        def _run() -> Any:
            if op == "identify":
                from notebooklm_tools.core.credential_store import get_current_backend_id

                return get_current_backend_id()
            elif op == "get":
                return backend.get_password(service, account)
            elif op == "set":
                backend.set_password(service, account, request["password"])
                return None
            elif op == "delete":
                backend.delete_password(service, account)
                return None
            elif op == "ensure_key":
                from notebooklm_tools.core.credential_store import (
                    BackendUnavailableError,
                    MissingKeyError,
                    get_current_backend_id,
                )

                backend_id = get_current_backend_id()
                current = backend.get_password(service, account)
                if current is not None:
                    return {"key": current, "created": False, "backend_id": backend_id}
                if not request.get("allow_create", True):
                    raise MissingKeyError(
                        f"Encryption key for account '{account}' is missing from OS keystore."
                    )
                candidate_key = request["candidate_key"]
                backend.set_password(service, account, candidate_key)
                readback = backend.get_password(service, account)
                if readback != candidate_key:
                    raise BackendUnavailableError(
                        "Failed to verify key persistence in OS store upon write"
                    )
                return {"key": candidate_key, "created": True, "backend_id": backend_id}
            elif op == "probe":
                import logging

                logger = logging.getLogger("notebooklm_tools.core.credential_store")
                probe_val = "probe_test"
                try:
                    backend.set_password(service, account, probe_val)
                    readback = backend.get_password(service, account)
                    return readback == probe_val
                finally:
                    try:
                        backend.delete_password(service, account)
                    except Exception as del_err:
                        logger.warning(
                            "Failed to delete keystore probe item %s: %s", account, del_err
                        )
            raise ValueError(f"Unknown operation: {op}")

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_run)
        try:
            return future.result(timeout=self._timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            executor.shutdown(wait=False, cancel_futures=True)
            msg = (
                f"OS credential store operation '{op}' timed out after {self._timeout_seconds}s. "
                "On macOS, approve the Keychain popup and retry, or run 'nlm auth storage status'."
                if is_desktop_session()
                else f"OS credential store operation '{op}' timed out after {self._timeout_seconds}s."
            )
            raise BackendTimeoutError(msg) from exc
        finally:
            executor.shutdown(wait=False)

    def _execute_in_helper(self, request: dict[str, Any]) -> Any:
        cmd = self._helper_cmd or [
            sys.executable,
            "-m",
            "notebooklm_tools.core.credential_backend_worker",
        ]

        # Preserve test isolation in child processes
        env = os.environ.copy()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self._last_helper_proc = proc

        input_data = json.dumps(request) + "\n"
        try:
            stdout_data, stderr_data = proc.communicate(
                input=input_data, timeout=self._timeout_seconds
            )
        except subprocess.TimeoutExpired as exc:
            proc.terminate()
            try:
                proc.communicate(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()

            msg = (
                f"OS credential store operation '{request.get('op')}' timed out after {self._timeout_seconds}s. "
                "On macOS, approve the Keychain popup and retry, or run 'nlm auth storage status'."
                if is_desktop_session()
                else f"OS credential store operation '{request.get('op')}' timed out after {self._timeout_seconds}s."
            )
            raise BackendTimeoutError(msg) from exc

        # Check stdout for structured response first
        response = None
        if stdout_data and stdout_data.strip():
            try:
                response = json.loads(stdout_data.strip())
            except json.JSONDecodeError:
                response = None

        if response is not None and not response.get("ok"):
            err_type = response.get("error_type", "")
            if err_type == "RealCredentialStoreAccessAttemptedError":
                raise RealCredentialStoreAccessAttemptedError(
                    "Real credential store access attempted in test"
                )
            if err_type == "KeystoreItemTooLargeError":
                raise KeystoreItemTooLargeError("Keystore item exceeds maximum allowed length")
            if err_type == "MissingKeyError":
                from notebooklm_tools.core.credential_store import MissingKeyError

                raise MissingKeyError(
                    response.get("error", "Encryption key is missing from OS keystore")
                )
            if err_type == "BackendUnavailableError":
                raise BackendUnavailableError("OS credential store is unavailable or locked")
            raise BackendUnavailableError("Credential store operation failed")

        if proc.returncode != 0:
            err_line = stderr_data.strip() if stderr_data else ""
            if "RealCredentialStoreAccessAttemptedError" in err_line:
                raise RealCredentialStoreAccessAttemptedError(
                    "Real credential store access attempted in test"
                )
            if "KeystoreItemTooLargeError" in err_line:
                raise KeystoreItemTooLargeError("Keystore item exceeds maximum allowed length")
            raise BackendUnavailableError("Credential store helper process failed")

        if response is None:
            raise BackendUnavailableError(
                "Invalid response received from credential helper process"
            )

        return response.get("result")


def _run_worker_loop() -> int:
    """Worker process main loop: read request JSON from stdin, output response JSON to stdout."""
    try:
        raw_input = sys.stdin.readline()
        if not raw_input:
            return 1
        request = json.loads(raw_input)
        op = request.get("op")
        service = request.get("service", "")
        account = request.get("account", "")

        result: Any = None

        if op == "identify":
            from notebooklm_tools.core.credential_store import get_current_backend_id

            result = get_current_backend_id()
        elif op == "get":
            backend = get_backend()
            result = backend.get_password(service, account)
        elif op == "set":
            backend = get_backend()
            password = request.get("password", "")
            backend.set_password(service, account, password)
        elif op == "delete":
            backend = get_backend()
            backend.delete_password(service, account)
        elif op == "ensure_key":
            from notebooklm_tools.core.credential_store import (
                BackendUnavailableError,
                MissingKeyError,
                get_current_backend_id,
            )

            backend_id = get_current_backend_id()
            backend = get_backend()
            current = backend.get_password(service, account)
            if current is not None:
                result = {"key": current, "created": False, "backend_id": backend_id}
            elif not request.get("allow_create", True):
                raise MissingKeyError(
                    f"Encryption key for account '{account}' is missing from OS keystore."
                )
            else:
                candidate_key = request["candidate_key"]
                backend.set_password(service, account, candidate_key)
                readback = backend.get_password(service, account)
                if readback != candidate_key:
                    raise BackendUnavailableError(
                        "Failed to verify key persistence in OS store upon write"
                    )
                result = {"key": candidate_key, "created": True, "backend_id": backend_id}
        elif op == "probe":
            import logging

            logger = logging.getLogger("notebooklm_tools.core.credential_store")
            backend = get_backend()
            probe_val = "probe_test"
            try:
                backend.set_password(service, account, probe_val)
                readback = backend.get_password(service, account)
                if readback != probe_val:
                    raise BackendUnavailableError("Keystore probe verification failed")
                result = True
            finally:
                try:
                    backend.delete_password(service, account)
                except Exception as del_err:
                    logger.warning("Failed to delete keystore probe item %s: %s", account, del_err)
        else:
            raise ValueError(f"Unknown operation: {op}")

        sys.stdout.write(json.dumps({"ok": True, "result": result}) + "\n")
        sys.stdout.flush()
        return 0
    except RealCredentialStoreAccessAttemptedError:
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "error": "Real credential store access attempted in test",
                    "error_type": "RealCredentialStoreAccessAttemptedError",
                }
            )
            + "\n"
        )
        sys.stdout.flush()
        return 2
    except KeystoreItemTooLargeError:
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "error": "Keystore item exceeds maximum allowed length",
                    "error_type": "KeystoreItemTooLargeError",
                }
            )
            + "\n"
        )
        sys.stdout.flush()
        return 3
    except BackendUnavailableError:
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "error": "OS credential store is unavailable or locked",
                    "error_type": "BackendUnavailableError",
                }
            )
            + "\n"
        )
        sys.stdout.flush()
        return 4
    except Exception as exc:
        if type(exc).__name__ == "MissingKeyError":
            sys.stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "error": str(exc),
                        "error_type": "MissingKeyError",
                    }
                )
                + "\n"
            )
            sys.stdout.flush()
            return 5
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "error": "Credential store operation failed",
                    "error_type": type(exc).__name__,
                }
            )
            + "\n"
        )
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    sys.exit(_run_worker_loop())
