# Getting Started

A practical guide to going from "just installed" to "Gemini Notebook (formerly Google NotebookLM) is wired
into my agent." For background on what the project is and the full feature
list, see the [README](../README.md). For deep command/tool reference, see
the [CLI Guide](CLI_GUIDE.md) and [MCP Guide](MCP_GUIDE.md).

## Contents

- [First-time setup](#first-time-setup)
- [Migrating from another Gemini Notebook MCP](#migrating-from-another-notebooklm-mcp)
- [Troubleshooting](#troubleshooting)

---

## First-time setup

If you have never used `notebooklm-mcp-cli` before, the path is:

1. **Install** — `uv tool install notebooklm-mcp-cli`. This gives you both
   the `nlm` CLI and the `notebooklm-mcp` server binary. See the
   [README → Installation](../README.md#installation) section for
   alternatives (`uvx`, `pip`, `pipx`, source install).
2. **Authenticate** — `nlm login`. The CLI extracts your Google cookies
   from a managed browser session. See the
   [Authentication Guide](AUTHENTICATION.md) for the supported methods
   and how multi-profile auth works.
   > 🔒 **Tip:** On a personal computer, encrypt your stored login in your computer's OS keystore with `nlm auth storage set protected`. See [Protected Storage](AUTHENTICATION.md#protected-storage).
3. **Connect an agent** — run the setup wizard and choose your app:
   ```bash
   nlm setup
   ```
   Choose **Add the MCP to my tools/agents**, tick your apps with Space, and
   press Enter. The wizard configures MCP at user/app scope, then offers the
   optional skill for all projects or the current folder. Use **Show my tools'
   status** to check what is connected, and **Copy MCP setup for a tool not
   listed** for a client without a built-in installer. For Claude Desktop's
   Chat and Cowork tabs (and claude.ai), tick **Claude Desktop / claude.ai** in
   **Add the skill** to get an upload file (`~/Downloads/nlm-skill.zip`).
4. **Verify** — restart your agent and call `notebook_list` (MCP) or
   `nlm notebook list` (CLI). If you see your existing notebooks, you are
   good to go.

For deeper coverage, jump to the relevant guide:

- [CLI Guide](CLI_GUIDE.md) — every command, every flag
- [MCP Guide](MCP_GUIDE.md) — every tool, every parameter
- [Authentication Guide](AUTHENTICATION.md) — login, profiles, token
  lifecycle, `auth_status` state meanings

---

## Migrating from another Gemini Notebook MCP

If you previously used a browser-automation–based Gemini Notebook MCP (or any
other third-party Gemini Notebook server) and want to switch to
`notebooklm-mcp-cli` for direct API access, follow these steps. Most agent
frameworks (Hermes Agent, Claude Code, Cursor, etc.) get confused when two
Gemini Notebook servers are configured at the same time because their tool
names overlap (`notebook_create`, `source_add`, …), so a clean swap is
recommended.

### 1. Install the unified CLI/MCP

```bash
uv tool install notebooklm-mcp-cli
```

This installs both `nlm` and the `notebooklm-mcp` server binary.

### 2. Authenticate once

```bash
nlm login
```

Your Google cookies are extracted from a managed browser session and
cached in `~/.notebooklm-mcp-cli/profiles/default/auth.json`. The
`nlm login --check` command verifies that the cached creds still work.

### 3. Register the new MCP server

Recommended: run the guided wizard to configure supported clients and
optionally install the skill:

```bash
nlm setup
```

The skill defaults to all projects (user level); choose the current folder for
project scope. For direct configuration, the existing client-specific commands
remain available. For example:

```bash
# Hermes Agent
nlm skill install hermes

# Claude Code
claude mcp add gemini-notebook-mcp -- notebooklm-mcp

# Gemini CLI
gemini mcp add --scope user gemini-notebook-mcp -- notebooklm-mcp

# Claude Desktop (detects regular and Relay AI/3P profiles)
nlm setup add claude-desktop
# Or select Relay AI / Claude 3P explicitly
nlm setup add claude-desktop --profile 3p
```

For any other MCP client, generate a config snippet:

```bash
nlm setup add json
```

> **Recommended server name:** `gemini-notebook-mcp`. The executable remains
> `notebooklm-mcp`. Avoid
> generic names like `notebooklm` if you also have a legacy server
> registered, or your agent will mix their tools up.

For Claude Desktop, fully quit the selected profile before running setup. If
both regular and Relay AI/3P profiles are detected, the CLI asks which one to
configure; if no profile exists, it creates nothing. Reopen Claude Desktop
after setup completes.

User-level skill installation also requires the target tool to be detected;
use `nlm skill install <tool> --level project` when you intentionally want a
project-local skill without changing user-level tool directories.

### 4. Remove the old MCP server

This is the step most people forget. Leaving both configured is the #1
cause of "Hermes picked the wrong tool" symptoms:

```bash
# Claude Code
claude mcp remove notebooklm          # (or whatever the old name was)

# Gemini CLI
gemini mcp remove notebooklm

# Hermes / others: edit the client config directly
```

> Only removing a *different* Gemini Notebook server needs this step. If the old
> entry is this project's own pre-rebrand name (`notebooklm-mcp` or
> `notebooklm`), `nlm setup` shows it as **⚠ old name** and renames it to
> `gemini-notebook-mcp` for you: **Add the MCP to my tools/agents → Needs a fix**.

If you are not sure what is registered, list everything:

```bash
claude mcp list                       # Claude Code
gemini mcp list                       # Gemini CLI
```

### 5. Restart your agent

Restart Claude Code / Cursor / Gemini / Hermes so the new tool list is
reloaded. Verify with a no-op call such as `notebook_list` (via the MCP)
or `nlm notebook list` (via the CLI).

---

## Troubleshooting

- **Auth setup issues** — see the
  [Authentication Guide → Troubleshooting](AUTHENTICATION.md#troubleshooting).
- **"Hermes picked the wrong tool"** — you almost certainly have two
  Gemini Notebook servers registered. See step 4 of the
  [migration section](#migrating-from-another-notebooklm-mcp) above.
- **`auth_status` says `"stale"`** — re-run `nlm login`. See
  [Understanding `auth_status`](AUTHENTICATION.md#understanding-auth_status)
  for the difference between `stale` and `unverified`.
- **Run the full diagnostic** — `nlm doctor` checks storage, auth, browser,
  and MCP wiring in one go.
