# GEMINI.md

## Project Overview

**Gemini Notebook (formerly Google NotebookLM) MCP Server & CLI**

This project implements a Model Context Protocol (MCP) server **and a full-featured Command Line Interface (CLI)** that provides programmatic access to [Gemini Notebook](https://notebook.google.com). It allows AI agents, developers, and power users to interact with Gemini Notebook notebooks, sources, query capabilities, and **download generated artifacts** (Audio, Video, PDF, etc.).

Tested with personal/free tier accounts. May work with Google Workspace accounts but has not been tested. This project relies on internal APIs (`batchexecute` RPCs).

## Environment & Setup

The project uses `uv` for dependency management and tool installation.

### Prerequisites
- Python 3.11+
- `uv` (Universal Python Package Manager)
- Google Chrome (for automated authentication)

### Installation

**From PyPI (Recommended):**
```bash
uv tool install notebooklm-mcp-cli
# or: pip install notebooklm-mcp-cli
```

**From Source (Development):**
```bash
git clone https://github.com/YOUR_USERNAME/notebooklm-mcp.git
cd notebooklm-mcp
uv tool install .
```

## Authentication

**Preferred: Run the automated authentication CLI:**
```bash
nlm login
```
This launches Chrome, you log in, and cookies are extracted automatically. Your login is saved to a Chrome profile for future use.

**Auto-refresh (v0.1.9+):**
The server now automatically handles token expiration:
1. Refreshes CSRF tokens on expiry (immediate)
2. Reloads cookies from disk if updated externally
3. Runs headless Chrome auth if profile has saved login

If headless auth fails (Google login fully expired), you'll see a message to run `nlm login` again.

**Explicit refresh (MCP tool):**
```
refresh_auth()  # Reload tokens from disk or run headless auth
```

**Fallback: Manual extraction (if CLI fails)**
If the automated tool doesn't work, extract cookies via Chrome DevTools:
1. Open Chrome DevTools on notebook.google.com
2. Go to Network tab, find a batchexecute request
3. Copy the Cookie header and call `save_auth_tokens(cookies=...)`

**Environment variable (advanced):**
```bash
export NOTEBOOKLM_COOKIES="SID=xxx; HSID=xxx; SSID=xxx; ..."
```

Cookies last for weeks. The server auto-refreshes as long as Chrome profile login is valid.

## Development Workflow

### Building and Running

**Reinstalling after changes:**
Because `uv tool install` installs into an isolated environment, you must reinstall to see changes during development.
```bash
uv cache clean
uv tool install --force .
```

**Running the Server:**
```bash
# Standard mode (stdio)
notebooklm-mcp

# Debug mode (verbose logging)
notebooklm-mcp --debug

# HTTP Server mode
notebooklm-mcp --transport http --port 8000
```

### Testing

Run the test suite using `pytest` via `uv`:
```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_api_client.py
```

## Project Structure

- `src/notebooklm_tools/`
    - `services/`: **Shared service layer (v0.3.0+)** — Business logic, validation, error handling
        - `errors.py`: Custom error hierarchy (`ServiceError`, `ValidationError`, etc.)
        - `chat.py`, `downloads.py`, `exports.py`, `notebooks.py`, `notes.py`: Domain services
        - `research.py`, `sharing.py`, `sources.py`, `studio.py`: More domain services
        - `batch.py`, `cross.py`, `pipeline.py`, `smart_select.py`: Batch, cross-notebook, pipeline, and tagging services
    - `cli/`: CLI commands and formatting (thin wrapper delegating to `services/`)
    - `mcp/`: MCP Server implementation (thin wrapper delegating to `services/`)
        - `tools/`: Modular tool definitions (one file per domain)
        - `server.py`: Slim server facade (imports tools from modules)
    - `core/client.py`: Low-level internal API calls (no business logic).
    - `core/constants.py`: Single source of truth for all API code-name mappings.
    - `core/auth.py`: Handles token validation, storage, and loading.
    - `utils/cdp.py`: Chrome DevTools Protocol for cookie extraction and headless auth.
    - `utils/`: Configuration and browser utilities
- `tests/services/`: Unit tests for all service modules (576+ tests)
- `CLAUDE.md`: Contains detailed documentation on the internal RPC IDs and protocol specifics. **Refer to this file for API deep dives.**
- `pyproject.toml`: Project configuration and dependencies.

## Key Conventions

- **Internal APIs:** This project relies on undocumented APIs. Changes to Google's internal API will break functionality.
- **RPC Protocol:** The API uses Google's `batchexecute` protocol. Responses often contain "anti-XSSI" prefixes (`)]}'`) that must be stripped.
- **Layering (v0.3.0+):** `cli/` and `mcp/` must NOT import from `core/` — delegate to `services/` instead. Services return TypedDicts and raise `ServiceError`/`ValidationError`.
- **New features:** Add low-level API in `core/client.py` → business logic in `services/*.py` → thin wrappers in `mcp/tools/*.py` and `cli/commands/*.py` → tests in `tests/services/`.
- **Constants:** All code-name mappings should be defined in `constants.py` using the `CodeMapper` class.

## Recent Additions

- **v0.4.6 Batch, Cross-Notebook, Pipelines & Smart Select**: Multi-notebook operations, cross-notebook aggregated queries, pipeline workflows, and tag-based notebook discovery. Contributed by @fabianafurtadoff (PR #90).
- **v0.4.6 MCP Tool Consolidation**: Consolidated 13 new tools into 4 action-based tools (`batch`, `pipeline`, `tag`, `cross_notebook_query`), keeping total MCP tools at 35.
- **v0.3.0 Service Layer Refactor**: Introduced shared `services/` layer with 10+ domain modules, eliminating duplicated logic between CLI and MCP. 576+ unit tests.
- **Skill Commands**: `nlm skill install/uninstall/list/show` for AI assistant integration
- **Verb-First Commands**: Alternative command style (`nlm install skill`, `nlm list skills`)
- **Interactive Artifact Downloads**: `download_quiz` and `download_flashcards` with JSON/Markdown/HTML formats
- **Sharing API**: `notebook_share_status`, `notebook_share_public`, `notebook_share_invite` for collaboration
