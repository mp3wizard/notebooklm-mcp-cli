"""Environment sanitization that must run before HTTP clients import."""

import os

_NO_PROXY_VARS = ("no_proxy", "NO_PROXY")


def sanitize_no_proxy_env() -> None:
    """Strip CIDR-style IPv6 entries from no_proxy that crash httpx's URL parser.

    Entries like fe11::/16 cause ValueError in httpx's normalize_port (encode/httpx#3221).
    Plain IPv6 addresses (::1) and host:port entries are intentionally preserved.
    """
    for var in _NO_PROXY_VARS:
        val = os.environ.get(var)
        if not val:
            continue
        parts = [p.strip() for p in val.split(",")]
        clean_parts = [p for p in parts if not ((":" in p) and ("/" in p))]
        if len(clean_parts) != len(parts):
            os.environ[var] = ",".join(clean_parts)


sanitize_no_proxy_env()
