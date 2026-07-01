# Security Scan Report — 2026-07-01

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-07-01T03:07Z
**Git HEAD:** 57e409f (post-merge v0.8.0)
**Trigger:** Daily upstream sync — v0.7.8 to v0.8.0 (3 commits merged)
**Standard:** OWASP APTS-aligned (Scope Enforcement, Auditability, Manipulation Resistance, Reporting)

## Upstream Changes Merged

| Version | Key Changes |
|---------|-------------|
| v0.8.0 (524ea92) | Short Video Overview format (`video_format="short"`); studio artifact source provenance; actionable file upload errors; "Refactor with NotebookLM" workflow docs; skill trigger updates |

### Commits in this merge
- `524ea92` **feat(video):** add Short Video Overview format; bump to 0.8.0
- `8a1c210` **docs(skill):** add trigger and workflow tree entry for document refactoring
- `9523f95` **docs(references):** add closed-loop "Refactor with NotebookLM" workflow (#239, @Grobiou)

## Merge Notes

No merge conflicts. Auto-merge via `ort` strategy. 27 files changed (187 insertions, 469 deletions). Notably: `run_log.txt` (425 lines) deleted and added to `.gitignore`.

## Tool Coverage

| Tool | Version | Status | Findings in project source |
|------|---------|--------|---------------------------|
| Gitleaks | 8.30.1 | ✅ OK | 0 secrets (622 commits, 10 MB) |
| TruffleHog | 3.95.6 | ✅ OK | 0 verified, 0 unverified (8124 chunks) |
| Bandit | 1.9.4 | ✅ OK | **src/:** 0 High, 0 Medium, 6 Low (try_except_pass — intentional error suppression in error-recovery paths); **tests/:** Low only (assert_used) |
| Semgrep OWASP | latest | ✅ OK | 0 (102 Python files, 153 rules) |
| Semgrep Python | latest | ✅ OK | 0 (102 Python files, 151 rules) |
| Semgrep Secrets | latest | ✅ OK | 0 (159 files; 1 PDF skipped >300 KB) |
| Trivy | 0.71.2 | ✅ OK | **0 vulnerabilities** (uv.lock, 88 pkgs) |
| OSV-Scanner | 2.4.0 | ✅ OK | 0 issues (88 packages) |
| config-audit | bundled | ✅ OK | CRITICAL/HIGH all false positives (scanner scripts flagging themselves; CLAUDE.md cookie docs; cc-beeper localhost hooks) |
| skill-audit | bundled | ✅ OK | 75/100 CRITICAL on SKILL.md — false positive (tool legitimately handles auth cookies for NotebookLM) |
| mcp-exfil-scan | bundled | ✅ OK | 0 exfiltration risks |
| skillspector | installed | ✅ OK | HIGH/MEDIUM all false positives — YARA info_stealer pattern matches legitimate Chrome CDP cookie extraction code |
| CodeQL | — | SKIPPED | Remote GitHub Actions only |
| mcp-scan | — | N/A | OPT-IN (sends data to invariantlabs.ai) |

## Dependency Vulnerabilities

**None.** Trivy and OSV-Scanner both report 0 issues across 88 packages in `uv.lock`. The security-upgraded lockfile from the prior session (2026-06-21) carried forward cleanly. No new vulnerable packages introduced by v0.8.0 merge.

## SAST Results

### Bandit (src/ only)

- **0 High** findings
- **0 Medium** findings
- **6 Low** — all `B110:try_except_pass` in `core/research.py` and `core/sources.py`; these are intentional — the except-pass blocks prevent error masking in recovery paths (comments explain context). No action needed.

### Semgrep

OWASP Top 10, Python ruleset, and Secrets ruleset all returned 0 findings across 102 Python files. Clean.

## Secret Scanning

- **Gitleaks:** 0 leaks across 622 commits (10 MB)
- **TruffleHog:** 0 verified / 0 unverified secrets (8124 chunks, git history mode)

## Skill / MCP Audit

- **mcp-exfil-scan:** 0 risks — no tool description poisoning, no outbound data flow, no exfil chains, no encoded payloads, no env var leaking
- **skillspector YR1 (info_stealer YARA):** 15 hits across `cdp.py`, `_utils.py`, `auth.py`, `AGENTS.md`, `CHANGELOG.md`, `CLAUDE.md` — all **confirmed false positives**. This tool is designed to extract Chrome cookies via CDP for NotebookLM authentication. The YARA pattern matches any credential-handling code regardless of legitimacy.
- **skill-audit SKILL.md score 75/100:** false positive — flagging the packaged `SKILL.md` for documenting credential/cookie handling, which is core project functionality.

## Large Files

One file >300 KB skipped by Semgrep: `mcps-audit-report.pdf` — not source code, no security concern.

## APTS Audit Log

- **Log:** `/tmp/css-scan-20260701T030328Z.jsonl`
- **Tool runs recorded:** 17 (measured: 17, asserted: 0)
- **Standard:** OWASP APTS § Auditability

## Overall Risk Posture

**Clean** ✅ — 0 dependency vulnerabilities; 0 SAST findings in project source; 0 secrets detected. All scanner findings are confirmed false positives arising from the tool's legitimate Chrome CDP authentication design. No fixes required.
