# Security Scan Report — 2026-05-04

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-05-04T10:55 ICT
**Git HEAD:** `b071dbd` (post-merge v0.6.3)
**Triggered by:** Upstream sync — v0.6.3 (CDP tab creation fallback #175) + GitHub Copilot setup support (#178)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

---

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    b071dbd
Include:     all supported
Exclude:     .gitignore honored by each tool
```

---

## Coverage

| Tool | Status | Version | Files / Packages | Findings |
|------|--------|---------|------------------|----------|
| Gitleaks | ✅ Ran | 8.30.1 | 507 commits, 9.15 MB | 0 |
| Bandit | ✅ Ran (src/) | 1.9.4 | 22,409 LOC | 0 actionable |
| Semgrep OWASP | ✅ Ran | latest | 101 files, 153 rules | 0 |
| Semgrep Python | ✅ Ran | latest | 101 files, 151 rules | 0 |
| Semgrep Secrets | ✅ Ran | latest | 140 files, 38 rules | 0 |
| Trivy (fs) | ✅ Ran | 0.69.3 | uv.lock | 0 vuln, 0 secrets |
| TruffleHog (git) | ✅ Ran | 3.94.2 | 7,046 chunks | 0 verified, 0 unverified |
| OSV-Scanner | ⚠️ N/A | 2.3.5 | (no package source detected) | — |
| config-audit (project CLAUDE.md) | ✅ Ran | bundled | — | 1 MEDIUM (false positive — project legitimately documents `cookies` for NotebookLM auth) |
| mcp-exfil-scan | ✅ Ran | bundled | — | 11 findings — **all OUT OF SCOPE** (target user's `~/.claude/skills/`, unchanged from previous scan) |

---

## Result: PROJECT CLEAN ✅

**0 in-scope findings at any severity (Very High / High / Medium / Low / Info).**

The merge from upstream v0.6.2 → v0.6.3 introduced no new vulnerabilities, secrets, or risky patterns into the project codebase. Net code delta is small and well-contained:

- `src/notebooklm_tools/utils/cdp.py` — added 30 lines for CDP tab-reuse fallback (#175)
- `src/notebooklm_tools/cli/commands/setup.py` — added 94 lines for GitHub Copilot setup target (#178)
- `tests/cli/test_setup_github_copilot.py` — new 217-line test file (#178)

All other diffs are version-string bumps (0.6.2 → 0.6.3) and documentation updates.

---

## Out-of-Scope Findings (Informational)

`mcp-exfil-scan` reports CRITICAL/HIGH findings against Anthropic-shipped skills under `~/.heuristics-without-source-attribution`:

- `~/.claude/skills/impeccable/SKILL.md` (CRITICAL × 1)
- `~/.claude/skills/security-audit/SKILL.md` (CRITICAL × 1)
- `~/.claude/skills/skill-security-auditor/SKILL.md` (HIGH × 3, MEDIUM × 1)
- `~/.claude/skills/atlas-cloud/SKILL.md` (HIGH × 2)
- `~/.claude/skills/playwright-cli`, `pyright`, `vtsls` (MEDIUM source-attribution × 3)

These are **identical to previous scan** and live outside the `notebooklm-mcp-cli` repository. Not actioned in this scheduled task — they belong to the user's broader Claude Code environment hardening, not this fork.

---

## Fixes Applied

None — no in-scope findings required action.

## Files Changed in This Cycle

Documentation only:
- `README.md` — "What's New" updated for v0.6.3
- `docs/security-scan-report-2026-05-04.md` — this report

---

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260504T035535Z.jsonl`
- **Tool runs recorded:** 8
- **Standard:** OWASP APTS § Auditability
