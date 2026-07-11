# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-11T02:41:00Z
**Git HEAD:** `7059fd3` (post-merge of origin/main v0.8.4 + v0.8.5)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    7059fd3
Include:     all supported (repo files, excluding .venv/.git)
Exclude:     .venv, .git (honored per-tool)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | 650 commits, ~10.2 MB | — |
| Bandit | OK | 1.9.4 | 38,028 LOC (`.venv` excluded) | — |
| Semgrep (owasp-top-ten) | OK | 1.168.0 | 106 files, 153 rules | 64 non-`.py`, 77 `.semgrepignore` |
| Semgrep (python) | OK | 1.168.0 | 106 files, 151 rules | same as above |
| Semgrep (secrets) | OK | 1.168.0 | 167 files, 38 rules | 1 file >300KB (`mcps-audit-report.pdf`), 77 `.semgrepignore` |
| Trivy | OK | 0.71.2 | `uv.lock` (88 packages) | — |
| TruffleHog | OK | 3.95.6 | 8,318 chunks / 10.5 MB (full git history) | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock` (88 packages) | — |
| CodeQL | SKIPPED | — | — | no `.github/workflows/codeql.yml` |
| mcps-audit | N/A | — | — | no runtime MCP server config in repo |
| config-audit (security-audit) | OK | v1.6.0 script | machine-wide `~/.claude` config | out-of-scope findings excluded from this report (see note) |
| skill-audit | OK | v1.6.0 script | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | OK | v1.6.0 script | machine-wide `~/.claude/skills` | no repo-local MCP/skill exfil vectors found; global findings out-of-scope |
| mcp-scan (opt-in) | SKIPPED | — | — | requires user consent (autonomous run, no user present) |
| skillspector LLM mode | SKIPPED | — | — | requires user consent (autonomous run, no user present) |

**Note on config-audit / mcp-exfil-scan:** both bundled scripts audit the *entire* `~/.claude` install (global settings, all installed skills/plugins), not just the scan target. All 63 config-audit findings and all 13 mcp-exfil-scan findings referenced files under `~/.claude/skills/*` or `~/.claude/settings.json` — none inside this repository. They are omitted from Findings below as out-of-scope; full raw tool output is preserved in the APTS audit log if needed.

## Findings — Very High / Critical
None.

## Findings — High
None.

## Findings — Medium

**1. Bandit B108 `hardcoded_tmp_directory` — 73 occurrences, all in `tests/`**
Test fixtures use literal `/tmp/...` paths (e.g. `tests/cli/test_login.py:11`, `tests/core/test_download.py:194`). Not production code; no untrusted input reaches these paths. **No fix required.**

**2. Bandit B102 `exec_used` — 1 occurrence, `tests/services/test_auth_service.py:153`**
```python
exec("from notebooklm_tools.services.auth import AuthManager", local_namespace)
```
Test-only dynamic import with a hardcoded, non-attacker-controlled string. **No fix required.**

**3. skill-audit — `src/notebooklm_tools/data/SKILL.md` scored 75/100 (tool verdict: CRITICAL)**
Two flagged patterns, both false positives given the skill's actual purpose (teaching the agent to use the NotebookLM auth CLI):
- *"Credential access"* — triggered by the word "credentials" in documentation describing `~/.notebooklm-mcp-cli/profiles/<name>/auth.json`, the tool's own documented storage location.
- *"Silent action instruction"* (Medium) — triggered by "Silently infer (user message → notebook title...) → one-line notice → `studio_create(confirm=True)`" (lines 66, 401). This describes skipping a clarifying-question round-trip, not a hidden/unconfirmed action — `studio_create` still requires `confirm=True`. Not a prompt-injection or exfiltration vector.

**No fix required** — both are pattern-matching false positives inherent to a skill whose subject matter is credential-based auth and UX-efficient defaults.

## Findings — Low / Info

- Bandit B101 `assert_used` — ~1,746 occurrences, exclusively in `tests/` (pytest idiom, expected).
- Bandit B108 low-confidence matches for further `/tmp` string literals in test mocks.

## Clean Scanners
Gitleaks, both Semgrep configs (owasp-top-ten, python, secrets), Trivy, TruffleHog, OSV-Scanner all returned **0 findings**. `notebooklm-cli.skill` scored 0/100 (LOW RISK / APPROVE).

## What Was Fixed
Nothing — no Medium/High/Very-High finding represented a real vulnerability. All are test-code idioms or pattern-matcher false positives on legitimate auth-CLI documentation.

## Cross-Tool Observations
No cross-tool overlaps within repo scope. config-audit and mcp-exfil-scan both independently flagged the same global `~/.claude/skills/*` files (out of scope here), which is expected since both scripts scan the same global config tree.

## Coverage Gaps
- Business logic / IDOR correctness not covered by SAST.
- Runtime behavior (actual NotebookLM RPC calls, CDP WebSocket handling under load) not exercised — static analysis only.
- `mcp-scan` and `skillspector` LLM-assisted mode skipped (opt-in, requires user consent not available in this autonomous run).
- `mcps-audit` had no applicable target — repo ships an MCP *server implementation*, not a client-side MCP config to audit.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260711T023741Z.jsonl`
- **Tool runs recorded:** 14
- **Standard:** OWASP APTS § Auditability
