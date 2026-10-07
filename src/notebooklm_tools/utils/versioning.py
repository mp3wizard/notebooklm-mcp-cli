"""Shared package-version comparison helpers."""

from packaging.version import InvalidVersion, Version


def is_newer_version(current: str, latest: str) -> bool:
    """Return whether latest is newer than current under PEP 440."""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False
