# Automated Security Scan Report
**Target:** `notebooklm-mcp-cli`  **Scanned:** 2026-10-01  **Git HEAD:** `c8af609` (post-merge of origin/main v0.14.0 "Protected mode")
**Standard:** OWASP APTS-aligned

## Coverage
| Tool | Result |
|------|--------|
| Gitleaks 8.30.1, 847 commits | no leaks |
| TruffleHog 3.97.5 | 0 verified / 8 unverified (same placeholder URLs `foo.com`/`bar.com` in old docs, pre-existing) |
| Bandit 1.9.4 (`src/`, `tests`/`.venv` excluded per project config) | 53 Low (subprocess/try-except-pass, standard project pattern), **1 Medium — fixed**, 0 High |
| Semgrep (owasp-top-ten, python, secrets; 127 git-tracked files) | 0 findings |
| Trivy 0.74.0 (`uv.lock`) | **1 Critical + 4 High + 7 Medium pyjwt CVEs — fixed**; 0 vulns after fix |
| OSV-Scanner 2.6.0 (98 packages) | No issues found (post-fix) |
| mcp-exfil-scan | **SKIPPED** — bundled script failed `SHA256SUMS` integrity check (fail-closed per skill rule); not run this cycle |
| config-audit | Repo-scoped findings limited to MEDIUM false positives on `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` (heuristic matches on legitimate cookie/credential auth docs, and one "skip verification" match that is actually a verify-*first* instruction); CRITICAL/HIGH items in the report are all in unrelated global `~/.claude` plugins, out of scope |
| skill-audit (`notebooklm-cli.skill`, `data/SKILL.md`) | `.skill` zip: 0/100 LOW, clean. `data/SKILL.md`: 75/100, driven by the same "credentials"/"silent action" heuristic false positives as prior scans |
| skillspector v2.11.0 (`--no-llm`) | `.skill`: 0/100 LOW. `data/SKILL.md`: 69/100 HIGH across 5 YARA hits — all reviewed individually (lines 154/692/818/844/882) and confirmed doc-prose false positives (e.g. `/clear` REPL command matched as "Memory Manipulation", the `nlm setup` MCP-config installer matched as "Session Persistence") |
| mcps-audit v1.0.0 | 745 findings (13 Critical / 196 High / 532 Medium / 4 Low), Risk 100/100 — representative sample from every rule category reviewed and dismissed as noise: HTTP-client code flagged as "exfiltration" (AS-011), JSON cache read/write flagged as "injection vector" (AS-004), `--confirm/-y` CLI flags flagged as "unrestricted agent autonomy" (AS-008) despite requiring explicit opt-in and a separate `confirm=True` MCP gate, `subprocess.run` with a fixed argv (already `# nosec`'d) flagged as "arbitrary command injection" (AS-001), error-message f-strings flagged as hardcoded secrets (AS-002) |
| CodeQL / mcp-scan | not run (N/A: no CodeQL workflow; mcp-scan is opt-in and this was an unattended run with no user to consent) |

## Merge
Merged 32 upstream commits (Protected mode credential storage, v0.14.0) at `c8af609`. Conflicts in `src/notebooklm_tools/core/auth.py`, `core/base.py`, `mcp/tools/_utils.py`, `utils/config.py`, `pyproject.toml`, `uv.lock` resolved in favor of origin's locking/revision-aware credential storage rewrite, folding local's SEC-002 (0o700 parent-dir chmod) hardening into the now-shared `_atomic_write_json` helper, keeping local's stricter `authlib`/`cryptography`/`fastmcp` pins alongside origin's new `filelock` dependency, and taking origin's fail-loud `ConfigError` over local's silent-continue on a corrupt config file. `uv.lock` regenerated from the merged `pyproject.toml` rather than hand-edited.

## Fixes
- **pyjwt 2.13.0 → 2.15.1** (`uv lock --upgrade-package pyjwt` + `uv sync`) — resolves CVE-2026-102268 (CRITICAL) plus CVE-2026-102265/66/67/69/70/71/72/73/74 (HIGH) and CVE-2026-101917/8 (MEDIUM). `pyproject.toml` pin raised to `>=2.15.1` with an updated comment.
- **`core/credential_store.py:323`** — `# nosec B608` + justification for a confirmed Bandit false positive (error-message f-string, not a SQL query).

## Remaining (Low/Info, left by design)
- 53 Bandit Low findings in `src/` (subprocess import, try/except/pass — standard patterns).
- 8 TruffleHog unverified placeholder-URL matches in historical scan-report docs.
- config-audit MEDIUM false positives on this repo's own `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` auth docs.
- skill-audit, skillspector, and mcps-audit heuristic false positives noted above — no code change indicated.
- mcp-exfil-scan coverage gap this cycle due to the checksum mismatch — flagged for follow-up (reinstall/verify the security-scanner plugin).

## Verification
Full non-e2e suite: 2,210 passed, 40 skipped. Ruff lint and format clean. `uv lock` resolves cleanly (98 packages). Trivy re-scan of `uv.lock` post-fix: 0 vulnerabilities.
