# Authentication Guide

This guide explains how to authenticate with Gemini Notebook (formerly Google NotebookLM) MCP and CLI.

> For public HTTP deployment or Claude web/mobile connectors, see
> [Remote MCP Deployment](REMOTE_MCP.md). Remote use introduces a separate MCP
> endpoint authentication requirement in addition to the Google browser session
> described here.

## Overview

Gemini Notebook uses browser cookies for authentication (there is no official API). The CLI/MCP extracts these cookies automatically from a managed browser session:

- Chromium-family browsers use Chrome DevTools Protocol (CDP)
- Firefox uses an isolated profile and reads its cookie store directly (no CDP or WebDriver required)

**Supported browsers**: Google Chrome, Arc (macOS), Dia (macOS) Brave, Microsoft Edge, Microsoft Edge Beta, Chromium, Firefox, Vivaldi, Opera.

On Windows, standalone Chromium is discovered in the standard machine-wide
locations under `C:\Program Files` and `C:\Program Files (x86)`, plus the
per-user `%LOCALAPPDATA%\Chromium\Application\chrome.exe` location. You can
select it explicitly with `nlm config set auth.browser chromium`.

**Two authentication methods are available:**

| Method                   | Best For                        | Requires                        |
| ------------------------ | ------------------------------- | ------------------------------- |
| **Auto Mode** (default)  | Most users                      | Any supported browser installed |
| **File Mode** (`--file`) | Complex setups, troubleshooting | Manual cookie extraction        |

---

## Method 1: Auto Mode (Recommended)

This method launches your browser automatically and extracts cookies after you log in.

### Prerequisites

- A supported browser installed (Chrome, Arc, Dia, Brave, Edge, Edge Beta, Chromium, Firefox, Vivaldi, or Opera)
- Chromium-family browsers should be **completely closed** before running

### Steps

```bash
# 1. Close your browser completely (Cmd+Q on Mac, or quit from taskbar)

# 2. Run the auth command (CLI or standalone)
nlm login                      # Recommended
#    New profile? It first asks: Protected (OS keystore, recommended) or Plain file.
#    See "Choosing at first login" under Protected Storage below.

# 3. Log in to your Google account in the browser window that opens
#    (Ctrl+C cancels cleanly: nothing is saved and the browser window is closed)

# 4. Wait for "Successfully authenticated!"
```

Chromium/CDP login waits up to 300 seconds for sign-in. A page at
`notebook.google.com`, an HTTP 200 response, or an anonymous `NID` cookie does
not prove authentication. Login waits for signed-in Google cookies and the
app's CSRF token before saving credentials or reporting success. A timeout
does not save anonymous credentials or replace an existing saved login.

### What Happens Behind the Scenes

1. The first available supported browser is detected (or your preferred browser if configured)
2. A dedicated browser profile is created for authentication
3. The browser launches with the appropriate automation backend
4. You log in to Gemini Notebook via the browser
5. Signed-in cookies and the CSRF token are extracted and cached; session fields are refreshed automatically when needed
6. Builtin login closes the browser it launched after successful extraction. Externally managed CDP browsers remain open.

### Recovering a Saved Session

If authentication has expired, retry login with the same profile, then check it:

```bash
nlm login --profile work
nlm login --check --profile work
```

In v0.15.3 and later, an anonymous session saved by an older version no longer
passes validation and blocks browser login. Upgrade first if an older version
reports success with only `NID` and no CSRF token. Profile deletion is not the
first recovery step. If a check is inconclusive because of a timeout or network
failure, check connectivity or try a read-only API call before re-authenticating.

When Firefox is selected, the profile is isolated under the NLM storage directory and its cookie database is read directly. Because cookie extraction cannot prove which Google account is active, re-login against an existing saved profile requires explicit `nlm login --force` after you confirm the account.

### Browser Preference

By default, `nlm login` uses the first available browser. To use a specific browser:

```bash
# Set preferred browser
nlm config set auth.browser brave

# Or use an environment variable
export NLM_BROWSER=arc

# Valid values: auto, chrome, arc, brave, edge, edge-beta, chromium, firefox, vivaldi, opera
# If the preferred browser is not installed, falls back to auto-detection.
```

### Persistent Login

The dedicated browser profile persists your Google login:

- **First run:** You must log in to Google
- **Future runs:** Already logged in, just extracts fresh cookies

This profile is separate from your regular browser profile. Chromium profiles disable extensions.

---

## Multi-Profile Support

Use multiple Google accounts by creating named profiles:

```bash
# Create profiles for different accounts
nlm login --profile work       # Opens browser - log in with work account
nlm login --profile personal   # Opens browser - log in with personal account

# List all profiles
nlm login profile list
# Output:
#   work: jsmith@company.com
#   personal: jsmith@gmail.com

# Switch default profile (no --profile flag needed)
nlm login switch personal
# Output: ✓ Switched default profile to personal

# Use profiles
nlm notebook list                    # Uses default (personal)
nlm notebook list --profile work     # Uses work account

# Manage profiles
nlm login profile rename work company
nlm login profile delete old-profile
```

### Switching accounts from an MCP app (no CLI needed)

AI apps that only have the MCP (for example Claude CoWork) can use the `profile` tool: list your saved accounts, switch for the current session, and optionally make a profile your saved default (`make_default=true`). A session switch lasts until the MCP server restarts. Apps like Claude Desktop share one MCP server across chats, so a switch can show up in other open chats until you quit and reopen the app. While a switch is active, every tool result names the account in use.

### How Multi-Profile Works

Each profile gets:

- **Separate credentials**: Stored in `~/.notebooklm-mcp-cli/profiles/<name>/`
- **Separate browser profile**: Isolated browser session in `~/.notebooklm-mcp-cli/chrome-profiles/<name>/`
- **Captured email**: Automatically extracted during login for easy identification

This means you can stay logged into multiple Google accounts simultaneously without conflicts.

---

## Unattended / Scheduled Refresh

A logged-in session normally self-heals: when the short-lived cookies age out,
the client automatically runs a headless-browser pass to make Google reissue
them. For unattended machines (a Mac mini or server running scheduled jobs),
you can also refresh proactively so a session never lapses between jobs:

```bash
nlm auth refresh                 # Refresh the default profile
nlm auth refresh --profile work  # Refresh a named profile
```

`nlm auth refresh` runs a headless browser against the saved profile — no
interactive login, no window to click. It exits non-zero when the refresh
fails, so a scheduler can react. Example launchd/cron keep-alive (every 30 min):

```bash
*/30 * * * * /path/to/nlm auth refresh >/dev/null 2>&1
```

> **Note:** This needs a saved Chrome profile (from a prior `nlm login`). It
> does not help when `NOTEBOOKLM_COOKIES` is set as an environment variable —
> that value overrides saved credentials, so update it directly instead.

> **Disabling the refresh:** Some Google Workspace accounts have their session
> revoked server-side whenever the saved browser profile is relaunched (issue
> #330). Set `NOTEBOOKLM_DISABLE_HEADLESS_REFRESH=1` to turn off both the
> automatic self-heal and `nlm auth refresh` on those accounts.

---

## Enterprise / Google Workspace

If your organization uses **Gemini Notebook Enterprise**, ask your Enterprise administrator for the project ID or number, the deployment location/multi-region, and confirmation that your account has access. Use the project- and location-specific host configured by your administrator (normally `notebook.cloud.google.com`). Set the base URL, project, and location before authenticating:

```bash
# Set the Enterprise URL and required Cloud resource context
export NOTEBOOKLM_BASE_URL=https://notebook.cloud.google.com
export NOTEBOOKLM_PROJECT_ID=your-gcp-project-id-or-number
export NOTEBOOKLM_LOCATION=global   # or us / eu, as provided by your administrator

# Then authenticate as usual
nlm login --profile enterprise
nlm login switch enterprise     # MCP uses the default profile
```

All CLI commands, MCP tools, and internal API calls will use this URL automatically. Enterprise requests require `NOTEBOOKLM_PROJECT_ID`; if the base URL is not set, the default personal URL (`https://notebooklm.google.com`) is used. The Enterprise variables apply to the current process, so use an Enterprise-only shell or MCP configuration when you also use a personal account.

> **Tip:** Add the export to your shell profile (`~/.zshrc`, `~/.bashrc`) so it persists across sessions.

For MCP server configuration, pass the variable in your client config:

```json
{
  "mcpServers": {
    "gemini-notebook-mcp": {
      "command": "notebooklm-mcp",
        "env": {
          "NOTEBOOKLM_BASE_URL": "https://notebook.cloud.google.com",
          "NOTEBOOKLM_PROJECT_ID": "your-gcp-project-id-or-number",
          "NOTEBOOKLM_LOCATION": "global"
        }
    }
  }
}
```

---

## The "Gemini Notebook" rebrand (`notebook.google.com`)

Google is rolling out a rebrand of Gemini Notebook that redirects some signed-in accounts to `notebook.google.com` instead of `notebooklm.google.com`. This is handled automatically: `nlm login` records whichever host accepts your account (per-profile, in `metadata.json`), and every CLI/MCP request is routed to that host afterward. No configuration is needed for personal accounts.

Resolution order, if you need to override it manually:

1. `NOTEBOOKLM_BASE_URL` env var, if set (see Enterprise section above).
2. The host your account last signed in on (auto-detected).
3. The default `https://notebooklm.google.com`.

---

## Method 2: File Mode

This method lets you manually extract and provide cookies. Use this if:

- Auto mode doesn't work on your system
- You have browser extensions that interfere (e.g., Google Antigravity IDE)
- You prefer manual control

### Steps

```bash
# Option A: Interactive mode (shows instructions, prompts for file path)
nlm login --manual

# Option B: Direct file path
nlm login --manual --file /path/to/cookies.txt
```

File mode verifies the imported cookies before saving them. For personal accounts, it checks both `notebooklm.google.com` and the rebranded `notebook.google.com`, then stores the host that accepts the session. Managed Workspace accounts should set `NOTEBOOKLM_BASE_URL` as described above.

To force the rebranded personal host explicitly:

```bash
NOTEBOOKLM_BASE_URL=https://notebook.google.com nlm login --manual --file /path/to/cookies.txt
```

### How to Extract Cookies Manually

1. Open Chrome and go to https://notebook.google.com
2. Make sure you're logged in
3. Press **F12** (or **Cmd+Option+I** on Mac) to open DevTools
4. Click the **Network** tab
5. In the filter box, type: `batchexecute`
6. Click on any notebook to trigger a request
7. Click on a `batchexecute` request in the list
8. In the right panel, scroll to **Request Headers**
9. Find the line starting with `cookie:`
10. Right-click the cookie **value** and select **Copy value**
11. Paste into a text file and save

### Cookie File Format

The cookie file should contain the raw cookie string from Chrome DevTools:

```
SID=abc123...; HSID=xyz789...; SSID=...; APISID=...; SAPISID=...; __Secure-1PSID=...; ...
```

**Notes:**

- Lines starting with `#` are treated as comments and ignored
- The file can contain the cookie string on one or multiple lines
- A template file `cookies.txt` is included in the repository
- Cookie files are static credentials. Re-export them when the live verification reports that they were rejected.

---

---

<a id="protected-storage"></a>
## Protected Storage (Protected Mode)

> 🔒 **New: Protected login storage (recommended)**
> Your saved Google login can now be encrypted, with its key kept in your computer's keychain instead of a plain file. We highly recommend everyone switch on a personal computer:
>
>     nlm auth storage set protected
>
> Optional: nothing changes unless you turn it on. Servers, cron, Docker and SSH setups can keep the plain file.
> [How it works](#protected-storage)

### Overview

By default, `notebooklm-mcp-cli` stores login cookies in readable JSON files (`file` mode) with `0600` permissions.

In **Protected mode**, your cookies and session tokens are encrypted on disk with AES-256-GCM (`credentials.enc`). The encryption key is generated uniquely for your computer and stored in your operating system's native keystore:
- **macOS:** macOS Keychain
- **Windows:** Windows Credential Manager
- **Linux:** SecretService API (GNOME Keyring, KWallet)

Protected mode is **optional**. File mode remains the default, and upgrading `notebooklm-mcp-cli` changes nothing until you explicitly choose to enable it.

### Choosing at first login

When you log in with a **new** profile in a terminal on a desktop computer, `nlm login` asks before the browser opens:

```
Where should your saved login live?
  1) Protected - encrypted, key kept in your OS keystore (recommended)
  2) Plain file - simple, readable by anything on this computer
```

Protected mode only accepts names made of letters, numbers, `-`, `_` and `.`. If you type something else (for example `my work` or `john@work.com`), the question offers a working name such as `my-work` and also lets you keep your name as a plain file. Choosing protected means the login is encrypted from the start and you will not be asked or reminded again. Choosing plain is respected too. Skip the question in scripts with `nlm login --storage protected` (or `--storage file`). Existing profiles keep their current mode; change it later with `nlm setup` (the "Credential protection" menu item) or `nlm auth storage set`.

### Commands

Manage credential storage using the `nlm auth storage` subcommands:

```bash
# Check current storage status for the default profile
nlm auth storage status

# Check a named profile
nlm auth storage status --profile work

# Switch to Protected mode (encrypts credentials, removes plain files)
nlm auth storage set protected
nlm auth storage set protected --profile work

# Switch back to File mode (decrypts credentials, restores readable JSON)
nlm auth storage set file
nlm auth storage set file --profile work

# Output status or results as JSON
nlm auth storage status --json
nlm auth storage set protected --json
```

### Conflict Resolution

If a profile has both plain-file credentials and encrypted credentials that differ (for example, if you logged in separately in both modes), `nlm` flags a conflict and asks you to resolve it:

```bash
# Keep the plain-file login and delete the encrypted leftover (stays in file mode)
nlm auth storage resolve file --profile work

# Keep the encrypted login and delete the plain files (switches to Protected mode)
nlm auth storage resolve protected --profile work

# Discard damaged or inaccessible credentials when the key is lost
nlm auth storage resolve file --profile work --discard-inaccessible --yes

# Clear a stuck or corrupt progress marker from an interrupted operation
nlm auth storage resolve --profile work --clear-marker --yes
```

- `resolve file`: Keeps your current plain-file login, deletes the encrypted leftover, and stays in file mode.
- `resolve protected`: Keeps the encrypted login, deletes the plain files, and switches to Protected mode.
- `--discard-inaccessible`: Use only when the encryption key was deleted from the OS keystore or the ciphertext file is corrupted beyond recovery. It removes the inaccessible ciphertext and resets the profile to file mode so you can log in again.
- `--clear-marker`: Clears a stuck or corrupt operation marker left behind if a migration was interrupted by a crash or power loss, provided the quarantine directory is clean.

### Relocating or Copying Storage

If you move your `~/.notebooklm-mcp-cli` directory to a new location on the same machine (e.g. changing your home directory path), update the installation identity:

```bash
nlm auth storage relocate
```

**Why a copied folder refuses:** Protected mode relies on your computer's OS keystore. If you copy `~/.notebooklm-mcp-cli` to a different machine, the new computer does not have the hardware-backed encryption key in its keystore. The profile safely refuses to open rather than crashing. To use Gemini Notebook on a new computer, sign in directly with `nlm login`.

### Downgrade Preparation

> [!WARNING]
> Older versions of `notebooklm-mcp-cli` do not understand `credentials.enc`. Before downgrading or installing an older version of the CLI, convert every protected profile back to file mode:
>
>     nlm auth storage set file
>     nlm auth storage set file --profile <name>

### Exporting Plain Credentials

If you need plain-text JSON credentials back (for example, to inspect them or use them with scripts that read `auth.json` or `cookies.json`), run:

```bash
nlm auth storage set file --profile <name>
```

This decrypts the credentials and writes readable JSON files with `0600` permissions.

### macOS "Always Allow" Prompt

Usually, no prompt appears during normal terminal operations. However, macOS prompts for permission when a different Python binary attempts to read an item created by another binary:

1. **Desktop extension users**: the Claude Desktop extension uses `python3` from `PATH` only to run a small launcher (`run_server.py`), which then starts the server with `uvx --from notebooklm-mcp-cli notebooklm-mcp`. `uvx` runs the server in its own environment, separate from `uv tool install`, and may pick a different Python build. If that Python differs from the one that created the key (for example, you enabled Protected mode from the `uv tool` install of `nlm`), macOS shows the Keychain access prompt once when the extension first reads it. Click **Always Allow** (not "Allow").
2. **Python upgrades**: If you upgrade Python (such as when Homebrew or `uv` installs a new Python release with a different binary path or signature), macOS detects the new binary signature and displays the prompt once more. Click **Always Allow** again.
3. Once **Always Allow** is clicked for each binary, macOS silently grants access for all future operations, MCP tool calls, and background token refreshes.

The prompt asks for your **Mac login password**: type it, then click **Always Allow**. If nobody answers within 60 seconds, `nlm` stops waiting and reports "approve the Keychain popup and retry", but the popup stays on screen. Dismiss it, rerun the command, and approve the new prompt.

### Where Protected Mode Cannot Work

Protected mode requires an active, interactive desktop session with an unlocked OS keystore. Remote and headless sessions cannot use the OS keystore (Keychain on macOS, Credential Manager on Windows). Specifically, it cannot work in:
- **Headless Linux servers, Docker containers, or cron jobs** without a D-Bus session bus.
- **Windows SSH sessions, Windows services, or Scheduled Tasks** set to "Run whether user is logged on or not" (Windows error 1312: Windows Credential Manager requires an interactive logon session).
- **macOS over SSH sessions** or prior to user login after a reboot (the macOS Keychain is locked or unavailable over remote SSH sessions).

If you run `nlm auth storage set protected` in an unsupported environment, it safely refuses with a clear error message:
> *Cannot enable protected mode: OS credential store is unavailable or locked.*
> *Remote/SSH sessions can't use the OS keystore (Keychain on macOS, Credential Manager on Windows). Run this from the desktop, or keep this profile in file mode. Your current setup keeps working.*

Your existing setup continues working in file mode. Keep automated, remote, and server profiles in file mode.

### Scheduled Refresh

User-configured scheduler jobs (`launchd`, `cron`, Windows Task Scheduler running `nlm auth refresh`) are the user's responsibility:
- In Protected mode, scheduled refresh only works while the user is logged into the OS desktop session with an unlocked keystore.
- Scheduled jobs running in headless environments, before login, or over SSH fail with a clear error unless the profile is kept in file mode.
- In-process token refresh and rotation (within an active CLI session or running MCP server process) is completely unaffected: it runs in the same Python process and requires no OS prompts.

### Threat Model

- **What it protects against:** Backups, cloud sync folders (Dropbox, iCloud, Google Drive), accidental sharing of repository or storage directories, and other tools or scripts that read files from disk.
- **What it does NOT protect against:** Other code running as your user account on the same computer (any process running under your user session can request the key from the OS keystore).
- **Other credential surfaces:** Protected mode secures `notebooklm-mcp-cli`'s stored credentials. It does not alter browser profiles (`chrome-profiles/`, Firefox SQLite databases), manual `cookies.txt` exports left on disk, `NOTEBOOKLM_COOKIES` environment variables in shell configs, legacy `~/.notebooklm-mcp/auth.json` files, or authenticated debug artifacts (`debug_page.html`).

### Environment Override (`NLM_AUTH_STORAGE`)

You can temporarily force the storage mode for testing using the `NLM_AUTH_STORAGE` environment variable (`file` or `protected`). If `NLM_AUTH_STORAGE` disagrees with the on-disk profile setting, mutating commands (`set` and `resolve`) refuse with an error until the variable is unset.

---

## Where Tokens Are Stored

All data is stored under `~/.notebooklm-mcp-cli/`:

```
~/.notebooklm-mcp-cli/
├── config.toml                    # CLI configuration
├── aliases.json                   # Notebook aliases
├── installation.json              # Installation identity
├── locks/                         # Inter-process profile locks
├── operations/                    # Migration state & quarantine markers
├── profiles/                      # Authentication profiles
│   ├── default/
│   │   ├── metadata.json          # Email, host, timestamps, storage mode
│   │   ├── credentials.enc        # Encrypted cookies & tokens (Protected mode)
│   │   └── cookies.json           # Plaintext cookies (File mode only)
│   ├── work/
│   │   ├── metadata.json
│   │   └── credentials.enc
│   └── personal/
│       ├── metadata.json
│       └── cookies.json
├── auth.json                      # Root mirror of default profile (File mode only)
├── chrome-profile/                # Chrome profile (single-profile users)
└── chrome-profiles/               # Chrome profiles (multi-profile users)
    ├── work/
    └── personal/
```

- In **Protected mode**, credentials live in `credentials.enc`. No plaintext cookies or `auth.json` files exist on disk.
- In **File mode**, credentials live in `cookies.json` (and the configured default profile is mirrored to root `auth.json` for backwards compatibility with external scripts), secured with `0600` permissions.
- In both modes, `metadata.json` stores non-secret profile metadata (account email, base host, build label, and storage mode setting).

---

## After Authentication

Once authenticated, add the MCP to your AI tool:

**Claude Code:**

```bash
claude mcp add gemini-notebook-mcp -- notebooklm-mcp
```

**Gemini CLI:**

```bash
gemini mcp add gemini-notebook-mcp notebooklm-mcp
```

**Manual (settings.json):**

```json
{
  "mcpServers": {
    "gemini-notebook-mcp": {
      "command": "notebooklm-mcp"
    }
  }
}
```

Then restart your AI assistant.

---

## Token Expiration

- **Cookies:** Generally stable for weeks, but some rotate on each request
- **CSRF token:** Auto-refreshed on each MCP client initialization
- **Session ID:** Auto-refreshed on each MCP client initialization

When you start seeing authentication errors, simply run `nlm login` again to refresh.

---

## Understanding `auth_status`

The MCP `server_info` tool and `nlm login --check` report one of five
`auth_status` values from the multi-probe AuthHealthChecker. Knowing the
difference matters: a `stale` status means you must re-auth, but
an `unverified` status is a network problem, not a credential problem.

> **Caching note:** the `server_info` result is cached for 30 seconds
> (the checker's `CACHE_TTL`) and bypassed on the next call if any auth
> file on disk is rewritten, so an external `nlm login` is reflected
> without waiting for the TTL. `nlm login --check` is always live.

| Status           | Meaning                                                                                                                                                                                          | What to do                                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `configured`     | Live check passed. Credentials are good.                                                                                                                                                         | Nothing.                                                                                                            |
| `not_configured` | No credentials are stored at all (first-time setup).                                                                                                                                             | Run `nlm login`.                                                                                                    |
| `stale`          | Credentials are known-bad: the live check was redirected to `accounts.google.com` (cookies expired), the on-disk profile failed to load, or the last successful validation is older than 7 days. | Run `nlm login` to refresh. Subsequent API calls will fail.                                                         |
| `unverified`     | The live check could not be completed (network timeout, DNS failure, proxy block, non-200 HTTP). Cached credentials on disk are still intact and may work for actual API calls.                  | Retry later, or check your network/proxy. Do not assume the user needs to re-auth — operations often still succeed. |
| `error`          | Unexpected exception inside the check itself (very rare).                                                                                                                                        | File a bug with the traceback.                                                                                      |

> **Heads up for AI agents:** If you see `auth_status = "stale"`, prompt the
> user to re-authenticate. If you see `auth_status = "unverified"` while
> recent operations are succeeding, treat it as a transient monitoring
> failure and continue — re-auth is not required.

---

## Troubleshooting

### "Browser is running but without remote debugging enabled"

Close your browser completely and try again. On Mac, use **Cmd+Q** to fully quit.

### Auto mode fails to connect

Try file mode instead:

```bash
nlm login --manual
```

### "401 Unauthorized" or "403 Forbidden" errors

Your cookies have expired. Run the auth command again to refresh.

### Browser opens with strange branding (e.g., Antigravity IDE)

Some browser extensions or tools modify the browser's behavior. Try a different browser or use file mode:

```bash
nlm login --manual
```

### Cookie file shows "missing required cookies"

Make sure you copied the cookie **value**, not the header name. The value should start with something like `SID=...` not `cookie: SID=...`.

### Authentication loop after `nlm login`

If you keep getting "Authentication expired" even after running `nlm login` or calling `refresh_auth`, check whether `NOTEBOOKLM_COOKIES` is set as an environment variable in your MCP config.

**Why this happens:** When `NOTEBOOKLM_COOKIES` is set in your config (e.g. `claude_desktop_config.json`), it takes priority over default auth sources — `auth.json`, profile cookies, `save_auth_tokens`, and `nlm login`. An explicit CLI `--profile` or MCP `usage_get(profile="work")` uses that saved account instead. When those hardcoded cookies expire, no recovery action can fix a running MCP process because the stale env var is baked into its environment.

**How to check:**

```python
import os
print("NOTEBOOKLM_COOKIES in env:", "YES (used when no explicit profile is selected)" if os.environ.get("NOTEBOOKLM_COOKIES") else "no")
```

**How to fix (pick one):**

1. **Update the cookie value** in your MCP config file with fresh cookies, then restart your AI tool (Claude Desktop, etc.)
2. **Remove the `NOTEBOOKLM_COOKIES` env var** from your config entirely and use `nlm login` instead (recommended — this way auth recovery works automatically)

Similarly, if you have `NOTEBOOKLM_CSRF_TOKEN` or `NOTEBOOKLM_SESSION_ID` in your config, remove them — both are deprecated and auto-extracted. Stale values can prevent auto-refresh from working.

---

### Experimental browser-backed RPC transport

`nlm doctor auth-replay` compares four lanes: saved cookies through httpx,
httpx after a forced cookie rotation, cookies freshly re-extracted from a
live logged-in browser (also replayed through httpx), and an in-page CDP
fetch from that same browser session. The fresh-cookie lane exists to tell
apart two failure modes that look identical if you only compare saved
cookies against the browser: ordinary expired cookies (verdict
`stale_cookies` — run `nlm login`, no transport needed) versus genuine
device-bound replay (verdict `browser_bound_replay` — even fresh cookies
fail outside the browser).

Only opt in to the experimental CDP transport if the verdict is
`browser_bound_replay`:

```bash
NOTEBOOKLM_RPC_TRANSPORT=cdp nlm notebook list
NOTEBOOKLM_RPC_TRANSPORT=cdp nlm query notebook <notebook-id> "Question?"
```

For MCP clients, add the same environment variable to the server config:

```json
{
  "mcpServers": {
    "gemini-notebook-mcp": {
      "command": "notebooklm-mcp",
      "env": {
        "NOTEBOOKLM_RPC_TRANSPORT": "cdp"
      }
    }
  }
}
```

This runs supported Gemini Notebook form POSTs through `fetch` inside the saved
Gemini Notebook browser profile, so the browser supplies its live cookies. It is
off by default and currently targets normal batchexecute RPCs plus notebook
chat. Uploads, downloads, and artifact file transfers still use the existing
HTTP paths.

If the CDP transport cannot find a saved profile-owned browser session, run
`nlm login` first. Do not use this flag as a general auth refresh shortcut;
use it only for suspected browser-bound replay failures.

---

## Chromium 136+ Compatibility

Chrome 136+ (and other Chromium-based browsers at the same version) restrict remote debugging on the default profile for security reasons. This is handled automatically by:

1. Using dedicated profile directories (`~/.notebooklm-mcp-cli/chrome-profiles/<name>/`)
2. Adding the `--remote-allow-origins=*` flag for WebSocket connections

No action required from users.

---

## Security Notes

- Cookies are stored locally in `~/.notebooklm-mcp-cli/profiles/<name>/auth.json`
- Each browser profile contains your Google login for Gemini Notebook
- Never share your `auth.json` files or commit them to version control
- The `cookies.txt` file in the repo is a template - don't commit real cookies
