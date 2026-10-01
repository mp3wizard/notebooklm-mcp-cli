"""Core functionality shared between CLI and MCP interfaces."""

from notebooklm_tools.core import constants

__all__ = ["load_cached_tokens", "save_tokens_to_cache", "constants"]


def __getattr__(name: str):
    if name in ("load_cached_tokens", "save_tokens_to_cache"):
        from notebooklm_tools.core import auth

        return getattr(auth, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
