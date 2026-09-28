# Guided `nlm setup` design

Date: 2026-09-27

## Purpose

Make initial MCP and skill setup usable without memorizing several commands. Running `nlm setup` with no subcommand opens one terminal wizard for adding, removing, or copying MCP configuration. Existing `nlm setup add/remove/list` and `nlm skill` commands remain available. The wizard excludes Alef Agent. Setup is an offline local configuration operation: it does not validate NotebookLM cookies, call NotebookLM APIs, or start the MCP server.

The expected user can recognize the AI app they use but should not need to know its configuration file format. A successful run reports what changed, where it changed, and whether an app restart is needed. A cancelled run does not make further changes.

## Entry and selection

Bare `nlm setup` opens a short first menu: **Add**, **Remove**, **Get JSON for another tool**, and **Exit**. Implement it with `no_args_is_help=False` and a Typer callback that runs only when no subcommand was invoked. It requires an interactive terminal. In a non-interactive terminal it prints the explicit commands to use, exits with status 1, and does not modify files. `nlm setup --help` continues to show help.

Add and Remove use a terminal checkbox selector. Add offers **Select all detected**; Remove offers **Select all found**. The displayed inventory includes the tool name, detected/configured state, and destination scope or path. Detection uses OS-appropriate app, command, and configuration signals; an existing skill directory alone is not evidence that its host app is installed. Undetected tools are not included in Add's Select all, and the JSON path remains available for unsupported tools.

Each selected tool receives a separate result. A failure in one tool does not stop later selected tools. The final summary distinguishes completed, already configured, skipped, and failed targets. Keyboard cancellation stops the remaining work, cleans up temporary files, summarizes any earlier completed changes, and exits with status 130.

## Add MCP

The wizard reuses the existing client setup functions and configuration formats. It installs at a user/app-level location by default and shows this as **All projects** where accurate. Current VS Code supports a user-profile MCP config as well as workspace `.vscode/mcp.json`; the wizard uses the user-profile location for GitHub Copilot to honor the global default. Prefer VS Code's supported `code --add-mcp` command when available. Resolve and show the destination profile/config path before mutation; if the active user profile cannot be identified safely, skip that target and explain how to use the VS Code UI. Preserve the existing project-scoped behavior of `nlm setup add/remove github-copilot`; add an explicit user-level scope option to those direct commands for parity with the wizard.

Codex CLI and the ChatGPT desktop app appear as one **Codex CLI / ChatGPT desktop app** target because they share `~/.codex/config.toml` on the same host. Detection recognizes either installed client: the `codex` command or Codex state for the CLI; `/Applications/ChatGPT.app` or `~/Applications/ChatGPT.app` on macOS; installed ChatGPT Store/package indicators on Windows; and the `chatgpt` executable or installed desktop package on Linux. A leftover skill directory alone does not count. The wizard configures one MCP entry and explains that it becomes available to both clients on that host. ChatGPT on the web is outside this local setup flow. `nlm setup add codex` retains its direct command, and `nlm setup add chatgpt-desktop` becomes an alias for the same shared operation.

For a new Codex entry, resolve the installed `notebooklm-mcp` executable to an absolute path **before** passing it to `codex mcp add`, and set `tool_timeout_sec = 300`, since NotebookLM operations can exceed Codex's 60-second default. Prefer the supported `codex mcp add` command when the CLI is available; update the resulting TOML with `tomlkit`, which preserves unrelated keys and comments. Treat those two steps as one target: if adding succeeds but setting the timeout fails, restore the prior config when safe, or report a partial change with the backup path rather than claiming success. When only the desktop app is present, update its shared TOML with the same library. Do not create an unusable entry when the server executable cannot be found. Existing entries are displayed as configured rather than silently replaced; offer a clearly described repair only when an invalid executable or insufficient timeout is detected.

After MCP setup, offer the optional skill with a brief explanation of its prompting and workflow references. First ask **All projects (user level)** or **This folder (project level)**, with All projects preselected. Then show eligible detected tools, preselecting those chosen for MCP setup and offering **All detected skill-capable tools**. Tools without a supported local skill location are labeled as such. Shared destinations are deduplicated: Codex CLI, ChatGPT desktop, and Gemini CLI use the `agents` skill location. Current OpenAI documentation explicitly lists `~/.agents/skills` and project `.agents/skills` for local Codex skills. Claude Code uses its local Claude skill location. Claude Desktop has account-based skills, but a local `~/.claude/skills` install is a Claude Code target; show Claude Desktop as MCP-only unless Claude Code is also detected. Alef Agent is excluded.

For each skill destination, inspect its installed version. Skip an equal or newer version. Ask before replacing an older or unversioned copy, showing its version when known. Back up the entire existing skill directory before any approved replacement or update; if backup fails, leave it unchanged. No existing skill is overwritten merely because the user selected All. The chosen level is shown in the final summary.

## Get JSON

Reuse the existing JSON generator's choices: `uvx` or installed executable, command name or full path when relevant, and an entry or complete `mcpServers` wrapper. Label the output as a generic snippet that the destination tool may require the user to adapt. Offer clipboard copy using a platform-available command (`pbcopy`, Windows clipboard, or a detected Linux clipboard utility). If copying is unavailable, keep the JSON visible and explain that it was not copied. This path does not edit client files.

## Remove and recovery

Remove scans for recognized Gemini Notebook MCP entries in the wizard's supported user/app-level locations and installed NLM skills at both user and current-project levels. It shows MCP entries and skills as separate selectable rows with exact paths and scopes. The user can remove either or both. Existing direct project-scoped removals remain available; the wizard does not scan every project on disk. It never deletes an unrelated MCP entry or an entire shared configuration file. The Codex desktop-only case must work without the `codex` executable by removing the recognized entry from the shared TOML.

Before mutation, display the selected items and request an explicit confirmation, defaulting to No. Skill removal receives a separate warning that deleting the active folder can discard personal edits. The warning lists each skill path. Existing Claude Desktop process guards remain in force so the app cannot immediately overwrite edits.

Before changing an existing configuration file, make a dated, uniquely named backup under `~/.notebooklm-mcp-cli/backups/` with private permissions. Back up an existing skill folder before deletion as well, so customized content can be recovered manually. If the relevant backup fails, skip that target without changing it. Replace the current JSON reader's silent `{}` fallback: missing files may start as `{}`, but malformed JSON/TOML must fail closed with a clear error and leave the original bytes intact. VS Code `mcp.json` may contain JSONC comments or trailing commas; prefer the supported VS Code command for addition and never rewrite a JSONC file as plain JSON. If a JSONC removal cannot preserve comments and unrelated entries, refuse the edit and show the exact file for manual removal.

For edits performed by `nlm`, write through a closed temporary file in the same directory, validate the result, preserve file permissions and unrelated settings, then call `os.replace`. Remove the temporary file on failure or interruption. For client-managed commands, back up their known user configuration files before invocation: `~/.codex/config.toml` for Codex and `~/.claude.json` for user-scoped Claude Code (not `~/.claude/settings.json`). Report each backup path in the result. No backup is needed when a new config file is being created. These safety helpers also protect the existing direct add/remove commands rather than only the wizard.

## Implementation boundaries and verification

Keep the wizard as a thin CLI coordinator. Reuse `setup.py` client operations, `skill.py` installation/version helpers, and existing platform path helpers. Add `questionary` for terminal checkbox selection and `tomlkit` for round-trip TOML edits rather than building those mechanisms from scratch. Extract small shared helpers where needed for detection, safe writes/backups, and skill actions; avoid a broad registry rewrite. Update CLI help and user documentation to make bare `nlm setup` the recommended path.

Tests cover add/remove menu choices, Select all, cancellation with status 130 and temporary-file cleanup, and non-interactive status 1; each OS's ChatGPT desktop detection; shared Codex/ChatGPT configuration, absolute executable and timeout; VS Code user-profile setup and an unknown-profile safe skip; user/project skill destinations, version decisions, deduplication, and backup before upgrade; JSON clipboard fallback; backup permission failures; malformed JSON/TOML and JSONC fail-closed behavior; preservation of unrelated config entries, comments, and permissions; desktop-only Codex TOML removal; and per-tool failure summaries. Run the CLI tests and full project test suite before calling the change complete.

Development takes place in an isolated worktree so the unpublished fixes currently being tested in the main checkout remain untouched. Integration with those fixes occurs only after their state is known.

## Platform references checked on 2026-09-27

- [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp): Codex CLI and the ChatGPT desktop app share local MCP configuration, and Codex supports a 300-second `tool_timeout_sec` override.
- [OpenAI local skill locations](https://learn.chatgpt.com/docs/build-skills): Codex loads user skills from `~/.agents/skills` and project skills from `.agents/skills`.
- [VS Code MCP configuration](https://code.visualstudio.com/docs/copilot/customization/mcp-servers): MCP servers can be installed in a user profile or a workspace; `code --add-mcp` supports the user profile.
- [Claude skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude): Claude account skills and Claude Code local skill files have different installation flows.
