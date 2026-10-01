"""Test-only launcher that injects fail-closed credential guards before running."""

from __future__ import annotations

import sys

import keyring

import notebooklm_tools.core.credential_store as cs
from notebooklm_tools.core.credential_store import (
    FailClosedCredentialBackend,
    FailClosedKeyring,
    RealCredentialStoreAccessAttemptedError,
    set_backend_factory,
)

# Install fail-closed guards in the subprocess
keyring.set_keyring(FailClosedKeyring())
set_backend_factory(lambda: FailClosedCredentialBackend())


def _fail_detect() -> cs.CredentialBackend:
    raise RealCredentialStoreAccessAttemptedError(
        "Subprocess OS backend access blocked in test launcher"
    )


cs._detect_os_backend = _fail_detect


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "-c":
        exec(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "nlm":
        from notebooklm_tools.cli.main import cli_main

        sys.argv = sys.argv[1:]
        cli_main()
    elif len(sys.argv) > 1:
        import runpy

        script_path = sys.argv[1]
        sys.argv = sys.argv[1:]
        runpy.run_path(script_path, run_name="__main__")


if __name__ == "__main__":
    main()
