# Security Scan Report — 2026-05-28 (post-merge v0.6.13)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD:** `36fa225` (Merge `origin/main` v0.6.11 → v0.6.13)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Coverage

| Tool | Version | Status | Findings |
|------|---------|--------|----------|
| Gitleaks | 8.30.1 | OK | 0 leaks (553 commits, 9.39 MB) |
| Bandit | 1.9.4 | OK | 5 Low / 0 Medium / 0 High (23 245 LOC) |
| Semgrep | (pipx) | OK | 0 findings (OWASP 153 + Python 151 + Secrets 38 rules) |
| Trivy fs | 0.69.3 | OK | 0 vulnerabilities, 0 secrets, 0 misconfigs |
| TruffleHog | 3.94.2 | OK | 0 verified, 0 unverified |
| OSV-Scanner | 2.3.5 | OK | 0 issues across 89 packages in `uv.lock` |
| config-audit | bundled | OK | 3 MEDIUM (false positives — see below) |
| skill-audit | bundled | OK | `notebooklm-cli.skill` 0/100 LOW · `data/SKILL.md` 35/100 MEDIUM (doc bash blocks only) |
| mcp-exfil-scan | bundled | OK (out of scope) | All 11 hits live in `~/.claude/skills/*` — user's global Claude config, not target repo |
| mcp-scan | uvx | SKIPPED | Opt-in (sends data to invariantlabs.ai); no consent in autonomous run |
| CodeQL | gh | SKIPPED | Not configured for this fork |

## Project-relevant findings

### Bandit — 5 × Low (accepted, not fixed)

All in `src/notebooklm_tools/utils/cdp.py`:

- **B404 / B603** — `subprocess` calls for Windows `taskkill` and `os.kill(pid, SIGTERM)`. Args are hardcoded, no shell, PID is an integer; safe by design.
- **B110** — `try / except / pass` around the kill call. Intentional best-effort cleanup; the docstring already states "safe to call multiple times."

No remediation required.

### config-audit — 3 × MEDIUM (false positives)

All hits target this repo's own `CLAUDE.md`, flagging the words *credentials* / *cookies* / *verify* in the troubleshooting section. This project is a NotebookLM cookie/auth manager — describing cookies in its documentation is core function, not a config issue. No action.

### skill-audit

- `notebooklm-cli.skill` → 0/100 **LOW** (no dangerous patterns, no prompt injection, no credential access)
- `src/notebooklm_tools/data/SKILL.md` → 35/100 **MEDIUM** — flagged only because the reference doc contains 27 bash code blocks. 0 dangerous patterns, 0 prompt injection, 0 credential access in actual content.

### mcp-exfil-scan — OUT OF SCOPE

All 11 findings (2 Critical, 5 High, 4 Medium) point to files under `~/.claude/skills/*` (the user's global Claude installation). These are not introduced by this merge and are not part of the target repo. Per APTS § Scope Enforcement, excluded from this report's verdict.

## Net effect of the merge on security posture

The merged upstream commits **strengthen** security:

| Improvement | PR / commit | Effect |
|-------------|-------------|--------|
| TOCTOU-safe credential file creation | PR #205 / `f2fb921` | Eliminates world-readable window between `open()` and `chmod()` |
| Debug log cookie redaction | PR #206 / `e0e7fbe`, `cecd757` | Prevents token disclosure via `--debug` output |
| GHA pinned to commit SHAs | PR #207 / `ff30a8a`, `06c648b` | Defends against tag-drift supply chain attacks |
| HTTP / SSE external-bind enforcement | v0.6.13 | Refuses `--host 0.0.0.0` unless explicit env opt-in |
| `terminate_chrome()` null-safety | PR #205 | Removes AttributeError edge case in cleanup path |
| Auth check consistency | PR #203 | Removes divergence between MCP and CLI auth status paths |

Merge conflict in `src/notebooklm_tools/core/auth.py::save_tokens_to_cache()` resolved by keeping **both** protections: local's `cache_path.parent.chmod(0o700)` (SEC-002 parent-directory restriction) **plus** upstream's TOCTOU-safe `os.open(..., 0o600)` for the file itself. Strictest combination.

## Verdict

**Overall risk posture: Clean.** No High / Medium severity findings in the target repo. Merge actively reduces attack surface. No remediation actions taken; 5 Bandit Lows left in place as accepted patterns documented above.

— Scan run: 2026-05-28T06:24Z
