# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NotebookLM MCP Server & CLI** - Provides programmatic access to NotebookLM (notebooklm.google.com) via both a Model Context Protocol server and a comprehensive command-line interface.

Tested with personal/free tier accounts. May work with Google Workspace accounts but has not been tested.

## Development Commands

```bash
# Install dependencies
uv tool install .

# Reinstall after code changes (ALWAYS clean cache first)
uv cache clean && uv tool install --force .

# Run the MCP server (stdio)
notebooklm-mcp

# Run with Debug logging
notebooklm-mcp --debug

# Run as HTTP server
notebooklm-mcp --transport http --port 8000

# Run tests (excludes e2e tests requiring live auth)
uv run pytest

# Run a single test
uv run pytest tests/test_file.py::test_function -v

# Run linting
uv run --dev ruff check .

# Run format check
uv run --dev ruff format --check .

# Auto-fix formatting
uv run --dev ruff format .
```

**Python requirement:** >=3.11

## Architecture

```
src/notebooklm_tools/
├── __init__.py          # Package version
├── services/            # Shared service layer — ALL business logic lives here
│   ├── errors.py        # ServiceError, ValidationError, NotFoundError, etc.
│   ├── batch.py         # Batch operations across multiple notebooks
│   ├── chat.py          # Chat/query logic
│   ├── cross_notebook.py # Cross-notebook query and aggregation
│   ├── downloads.py     # Artifact downloading
│   ├── exports.py       # Google Docs/Sheets export
│   ├── notebooks.py     # Notebook CRUD + describe
│   ├── notes.py         # Note CRUD
│   ├── pipeline.py      # Multi-step notebook workflows
│   ├── research.py      # Research start/poll/import
│   ├── sharing.py       # Public link, invite, status
│   ├── smart_select.py  # Tag-based notebook selection
│   ├── sources.py       # Source add/list/sync/delete
│   └── studio.py        # Artifact creation, status, rename, delete
├── cli/                 # CLI commands and formatting (thin wrapper)
│   └── commands/        # One file per domain (notebook.py, source.py, etc.)
├── mcp/                 # MCP server + tools (thin wrapper)
│   ├── server.py        # FastMCP server facade + /health endpoint
│   └── tools/           # One file per domain; _utils.py for shared helpers
├── core/                # Low-level API client — no business logic
│   ├── client.py        # Google batchexecute RPC calls
│   ├── base.py          # HTTP session, auth headers, page fetch
│   ├── auth.py          # AuthManager for profile-based token caching
│   ├── constants.py     # CodeMapper (RPC code ↔ human name mappings)
│   └── data_types.py    # Typed response structures
└── utils/
    ├── config.py        # Configuration and storage paths (~/.notebooklm-mcp-cli/)
    └── cdp.py           # Chrome DevTools Protocol for cookie extraction / nlm login
```

**Strict Layering Rules:**
- `cli/` and `mcp/` are thin wrappers: handle UX (prompts, spinners, JSON output) and delegate to `services/`
- `services/` contains all business logic and validation. Returns typed dicts.
- `cli/` and `mcp/` must **NOT** import from `core/` directly — always go through `services/`
- `services/` raises `ServiceError`/`ValidationError` — never raw exceptions
- MCP tool list parameters must go through `coerce_list()` from `mcp/tools/_utils.py` — MCP clients often serialize lists as JSON strings or comma-separated values

**Storage Structure (`~/.notebooklm-mcp-cli/`):**
```
├── config.toml                    # CLI settings (default_profile, output format)
├── aliases.json                   # Notebook aliases
├── profiles/<name>/auth.json      # Per-profile credentials and email
├── chrome-profile/                # Chrome session (single-profile/legacy)
└── chrome-profiles/<name>/        # Chrome sessions (multi-profile)
```

**Executables:**
- `nlm` - Command-line interface
- `notebooklm-mcp` - The MCP server

## Test Structure

```
tests/
├── services/      # Unit tests for each service module (primary test suite)
├── core/          # Unit tests for low-level API client logic
├── cli/           # Unit tests for CLI formatting and command logic
├── test_e2e.py    # Marked @pytest.mark.e2e — requires live auth, skipped in CI
└── test_mcp_e2e.py
```

CI runs `pytest -m "not e2e"` — E2E tests are excluded. When adding a new service, add corresponding tests in `tests/services/`.

## Authentication

**You only need to provide COOKIES.** The CSRF token and session ID are automatically extracted.

### Method 1: Chrome DevTools MCP (Recommended)

```python
# Fast path — extract from a batchexecute network request:
save_auth_tokens(
    cookies=<cookie_header>,
    request_body=<request_body>,  # Contains CSRF token
    request_url=<request_url>      # Contains session ID
)
```

### Method 2: Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTEBOOKLM_COOKIES` | Yes | Full cookie header from Chrome DevTools |
| `NOTEBOOKLM_BL` | No | Override build label (auto-extracted from page) |
| `NOTEBOOKLM_HL` | No | Interface language (default: `en`) |

`NOTEBOOKLM_CSRF_TOKEN` and `NOTEBOOKLM_SESSION_ID` are deprecated — auto-extracted now.

When API calls fail with auth errors, re-extract fresh cookies from Chrome DevTools.

## MCP Tools

Tools requiring `confirm=True` (irreversible operations): `notebook_delete`, `source_delete`, `studio_delete`, `note_delete`, `source_sync_drive`, `studio_create`, `studio_revise`.

New in v0.4.6+: `batch`, `cross_notebook_query`, `pipeline`, `tag` (consolidated tools with `action` parameter).

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| 401/403 | Cookies expired | Re-extract from Chrome DevTools |
| "Invalid CSRF token" | `at=` value expired | Re-extract cookies |
| Empty notebook list | Wrong Google account | Verify account in cookies |
| Rate limit | Free tier ~50 queries/day | Wait or upgrade |

## Contributing

When adding new features:

1. Capture the network request with Chrome DevTools MCP
2. Document the RPC ID in `docs/API_REFERENCE.md`
3. Add the low-level method in `core/client.py`
4. Add business logic in the appropriate `services/*.py`
5. Add thin wrappers in `mcp/tools/*.py` and `cli/commands/*.py`
6. Write unit tests in `tests/services/`
7. Add test cases to `docs/MCP_CLI_TEST_PLAN.md`

## Documentation

- **`docs/API_REFERENCE.md`** — RPC IDs, parameter structures, response formats. Read when debugging API issues or adding features.
- **`docs/MCP_CLI_TEST_PLAN.md`** — Step-by-step test cases for all MCP tools and CLI commands.
