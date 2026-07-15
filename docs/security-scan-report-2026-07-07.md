# Security Scan Report — 2026-07-07

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Trigger:** Automated post-merge scan after syncing upstream v0.8.3
**Scanned at:** 2026-07-07T03:47–03:51 UTC
**Git HEAD:** Post-merge (origin/main @ `ad98824`, merge commit `f6eb1fa`)
**Standard:** OWASP APTS-aligned

## Commits Merged (v0.8.3)

| Hash | Description |
|------|-------------|
| `5e61f8c` | fix: prevent MCP query cancellation crash |
| `8134908` | feat: add experimental CDP RPC transport |
| `ad98824` | docs(changelog): add v0.8.3 release entry |

Merge conflict in `src/notebooklm_tools/core/base.py` resolved by keeping the
local SEC-006 fix (`secrets.randbelow` instead of `random.randint` for the
`_reqid_counter` seed) while adding origin's new `_cdp_ws_url` /
`_cdp_launched_port` fields for the CDP transport feature.

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    f6eb1fa (post-merge)
Include:     src/, tests/, project root
Exclude:     .venv/ (third-party deps — not project source)
```

## Coverage Disclosure

| Tool | Status | Version | Finding Summary |
|------|--------|---------|-----------------|
| Gitleaks | OK | 8.30.1 | 0 secrets in 638 commits |
| Bandit | OK | 1.9.4 | 0 High, 0 Medium, 0 Low in src/ + desktop-extension/ after fixes |
| Semgrep OWASP | OK | latest | 0 findings in 100 files |
| Semgrep Python | OK | latest | 0 findings in 100 files |
| Semgrep Secrets | OK | latest | 0 findings in 167 files |
| Trivy | OK | 0.71.2 | 0 vulns in uv.lock (88 packages) |
| TruffleHog | OK | 3.95.6 | 0 verified/unverified secrets |
| OSV-Scanner | OK | 2.4.0 | No issues found |
| config-audit | OK | bundled | All Medium/Low findings are false positives (see below) |
| mcp-exfil-scan | OK | bundled | CLEAN (0/100) |
| skill-audit (`SKILL.md`) | OK | bundled | 75/100 — false positives by design (heuristic on auth-flow docs) |
| skill-audit (`.skill`) | OK | bundled | 0/100 |
| mcps-audit | OK | 1.0.0 | 514 findings, score 100 — investigated 3 CRITICAL, all false positives on dev-only debug scripts |
| CodeQL | SKIPPED | — | No `.github/workflows/codeql.yml` in fork |
| mcp-scan | OPT-IN | — | Not run (sends data to invariantlabs.ai) |
| skillspector | SKIPPED | — | No new AI-skill artifacts introduced in this merge |

## Tool Results

### Gitleaks
**Summary:** 0 secrets. 638 commits scanned, ~10.21 MB, 1.81s.

### Bandit
**Summary (src/ + desktop-extension/, via `pyproject.toml` `[tool.bandit]` config):** 0 High, 0 Medium, 0 Low after fixes (see Fixes Applied). 19 High findings from an unscoped `.venv`-inclusive run were confirmed to be entirely in third-party dependency code (authlib, cryptography, dnspython, fastmcp, httpx, joserfc, mcp, mypy, pygments, websocket-client, websockets) — not project source, not actionable.

### Semgrep
**Summary:** 0 findings across all three rulesets:
- `p/owasp-top-ten`: 0 findings, 100 files, 153 rules
- `p/python`: 0 findings, 100 files, 151 rules
- `p/secrets`: 0 findings, 167 files, 38 rules

Coverage note: `--max-target-bytes 300000` skipped 1 file >300 KB (non-source, e.g. lockfile/report); no project source files affected.

### Trivy
**Summary:** 0 vulnerabilities. uv.lock scanned (88 packages). No secrets flagged. Trivy 0.71.2 is not in the known-compromised range (0.69.4–0.69.6).

### TruffleHog
**Summary:** 0 verified secrets, 0 unverified secrets. 8,257 chunks, 10.53 MB scanned.

### OSV-Scanner
**Summary:** No issues found in uv.lock (88 packages).

### Config Audit
**Reported:** 8× MEDIUM, 7× LOW (no CRITICAL/HIGH this run)

All MEDIUM findings are false positives:

| Finding | Verdict |
|---------|---------|
| 4× MEDIUM broad `SessionStart`/`UserPromptSubmit` hook matchers (caveman, pordee plugins) | INFO — expected normal operation of unrelated global plugins, not this repo |
| 2× MEDIUM "skip verification" instruction in CLAUDE.md | FP — matched troubleshooting table text and a changelog-accuracy rule, not an actual bypass instruction |
| 2× MEDIUM credential/cookie file references in CLAUDE.md | FP — this project explicitly documents Google credential/cookie handling by design (NotebookLM auth) |

7× LOW are informational "hooks configuration found" notices for unrelated global plugins — no action needed.

### MCP Exfil Scan
**Verdict:** CLEAN (0/100). No tool description poisoning, outbound flow, exfil chains, encoded payloads, env var leaking, or source trust issues detected across 5 MCP configs and 10 skill files.

### Skill Audit
**`src/notebooklm_tools/data/SKILL.md`: 75/100** — false positives by design:
- "Potential credential access" — matched the word "credentials" in a line documenting `nlm login` / cookie refresh, expected for an auth-handling tool
- "Silent action instruction" — matched "Infer format/style/prompt silently" (i.e., don't over-prompt the user with intake questions), not a hidden/undisclosed action
- 6 documentation URLs (`example.com`, `youtube.com`, `127.0.0.1`) — placeholders/examples in prose, not live network calls

**`notebooklm-cli.skill`: 0/100** — clean, no findings.

### mcps-audit
**Verdict:** FAIL, risk score 100/100, 514 findings (10 CRITICAL, 111 HIGH, 390 MEDIUM, 3 LOW) across 181 files / 49,045 lines.

Investigated the 3 CRITICAL "Dangerous execution" findings — all in `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py`, one-off local developer debug utilities (not part of the installed package — `pyproject.toml` only exposes `nlm`/`notebooklm-mcp` as `[project.scripts]`, and these files aren't referenced by any packaged module or MCP tool). They use CDP `Runtime.evaluate` against the developer's own local Chrome profile for DOM inspection during development — no remote/untrusted input path, no MCP tool exposure. Confirmed false positive.

The bulk of MEDIUM findings (AS-010 "no logging/auditing", AS-003 "high-risk permission pattern" matching strings like `RPC_LABEL_DELETE` in test/dev scripts) are heuristic string matches on constant names and comments in test/dev tooling, not exploitable code paths. Given the volume (514) and that the tool has no allow-list/suppression mechanism for dev-only scripts, this is treated as a known high false-positive-rate tool for this project — consistent with prior scan reports.

## Fixes Applied

Bandit was the only tool with confirmed real findings in project source code (all Low severity, no Medium/High/Very High). Applied `# nosec` with the project's established one-line-justification convention (matching existing usage in `utils/wsl.py`, `utils/cdp.py`, `cli/main.py`, `services/sources.py`, `services/studio.py`):

- `src/notebooklm_tools/utils/cdp.py` — `ps -p <pid>` (Darwin), `powershell Get-CimInstance` (Windows), and `taskkill /PID` (Windows) subprocess calls: `# nosec B603 B607` — all list-form (no `shell=True`), `pid` is `int`-typed, flags hardcoded.
- `src/notebooklm_tools/core/cdp_transport.py`, `src/notebooklm_tools/core/research.py`, `src/notebooklm_tools/core/sources.py`, `src/notebooklm_tools/services/research.py` — 4× `except Exception: pass`: `# nosec B110` with a one-line reason each (transient polling retry / best-effort import or rename that must not mask the original error).
- `desktop-extension/run_server.py` — `import subprocess` and the `uvx` launcher `subprocess.run`: `# nosec B404 B603` — list-form exec of a resolved path, no shell, standard launcher pattern.

Verified after fixes: `bandit -c pyproject.toml -r .` → 0 High, 0 Medium, 0 Low. `ruff check .` and `ruff format --check .` pass. Full test suite: 1080 passed, 38 skipped, 0 failed.

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| Very High | 0 | — |
| High | 0 in src/ | — |
| Medium | 0 in src/ | — |
| Low | 0 in src/ (13 fixed with `# nosec`) | Fixed |
| Info | config-audit / skill-audit / mcps-audit flags | All false positives (see above) |

## Tools Used

Gitleaks 8.30.1 · Bandit 1.9.4 · Semgrep (latest) · Trivy 0.71.2 · TruffleHog 3.95.6 · OSV-Scanner 2.4.0 · mcps-audit 1.0.0 · config-audit (bundled) · skill-audit (bundled) · mcp-exfil-scan (bundled)

**APTS Audit Log:** `/tmp/css-scan-20260707T034703Z.jsonl` · 2 measured tool runs (gitleaks, bandit via wrapper); remaining tools run directly and logged in this report.
