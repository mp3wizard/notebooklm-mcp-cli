# Security Scan Report — 2026-07-02

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Trigger:** Automated post-merge scan after syncing upstream v0.8.1
**Scanned at:** 2026-07-02T02:37–02:42 UTC
**Git HEAD:** Post-merge (origin/main @ `8c8a14b`)
**Standard:** OWASP APTS-aligned

## Commits Merged (v0.8.1)

| Hash | Description |
|------|-------------|
| `1b042d9` | fix: prevent login --check crash on slow accounts (Fixes #243) |
| `45143b3` | fix(cdp): verify mapped Chrome owns NLM profile before reuse (Fixes #244) |
| `55cceaf` | fix(cdp): require exact mapped Chrome flags |
| `8c8a14b` | chore: prepare v0.8.1 maintenance release |

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    post-merge (627 commits)
Include:     src/, tests/, project root
Exclude:     .venv/ (third-party deps — not project source)
```

## Coverage Disclosure

| Tool | Status | Version | Finding Summary |
|------|--------|---------|-----------------|
| Gitleaks | OK | 8.30.1 | 0 secrets in 627 commits |
| Bandit | OK | 1.9.4 | 0 High/Medium in src/; High findings all in .venv |
| Semgrep OWASP | OK | latest | 0 findings in 97 files |
| Semgrep Python | OK | latest | 0 findings in 97 files |
| Semgrep Secrets | OK | latest | 0 findings in 105 files |
| Trivy | OK | 0.71.2 | 0 vulns in uv.lock (88 packages) |
| TruffleHog | OK | 3.95.6 | 0 verified/unverified secrets |
| OSV-Scanner | OK | 2.4.0 | No issues found |
| config-audit | OK | bundled | LOW only (hooks config — expected) |
| mcp-exfil-scan | OK | bundled | CLEAN (0/100) |
| skillspector | OK | 2.1.4 | CRITICAL score but all findings are false positives (see below) |
| skill-audit | OK | bundled | Score on scanner's own SKILL.md — not project code |
| CodeQL | SKIPPED | — | No .github/workflows/codeql.yml in fork |
| mcps-audit | SKIPPED | — | No .skill files requiring mcps-audit |
| mcp-scan | OPT-IN | — | Not run (sends data to invariantlabs.ai) |

## Tool Results

### Gitleaks
**Summary:** 0 secrets. 627 commits scanned, 10.11 MB, 1.88s.

### Bandit
**Summary (src/ only):** 0 High, 0 Medium, 1,653 Low — all Low findings in src/ are `B101` (assert in tests, expected) and `B108` (hardcoded `/tmp` in one test file for a nonexistent path).

High findings in full scan were exclusively in `.venv/` (third-party packages: authlib SHA1 use, dns SHA1, httpx SHA1, fastmcp SHA1 for module naming, jaraco tarfile extraction, joserfc pyCrypto import). None are in project source.

### Semgrep
**Summary:** 0 findings across all three rulesets:
- `p/owasp-top-ten`: 0 findings, 97 files, 153 rules
- `p/python`: 0 findings, 97 files, 151 rules
- `p/secrets`: 0 findings, 105 files, 37 rules

Coverage note: `mcps-audit-report.pdf` (>300 KB) skipped by `--max-target-bytes`; not a source file.

### Trivy
**Summary:** 0 vulnerabilities. uv.lock scanned (88 packages). No secrets flagged.

### TruffleHog
**Summary:** 0 verified secrets, 0 unverified secrets. 8,155 chunks, 10.44 MB scanned.

### OSV-Scanner
**Summary:** No issues found in uv.lock (88 packages).

### Config Audit
**Findings (LOW only):**
- `~/.claude/settings.json` — hooks configuration (expected: PostToolUse, PreToolUse, UserPromptSubmit etc.)
- Various plugin hook files (normal plugin operation)

### MCP Exfil Scan
**Verdict:** CLEAN (0/100). No tool description poisoning, outbound flow, exfil chains, encoded payloads, env var leaking, or source trust issues detected.

### Skillspector
**Score:** 100/100 CRITICAL (all false positives).

Flagged findings:
- `tests/core/test_utils.py:3` — imports `extract_cookies_from_chrome_export` — YARA `info_stealer` trigger. **False positive:** this is Chrome CDP authentication utility code by design (the tool legitimately reads cookies for NotebookLM auth).
- `tests/test_auth_migration.py:651` — class `TestPageFetchHeaders` referencing `_PAGE_FETCH_HEADERS`. **False positive:** test class for platform-neutral header regression (Issue #105).

Both findings are YARA pattern matches on legitimate auth-related identifiers. No malicious behavior.

## Fixes Applied

**None required.** Zero vulnerabilities found in project dependencies (Trivy, OSV-Scanner). Zero exploitable SAST findings in project source (Semgrep, Bandit).

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| Very High | 0 | — |
| High | 0 in src/ | .venv only (third-party, not actionable) |
| Medium | 0 in src/ | — |
| Low | 1,653 in src/+tests/ | All B101/B108 in test code — not actionable |
| Info | hooks config audit | Expected |

## Tools Used

Gitleaks 8.30.1 · Bandit 1.9.4 · Semgrep (latest) · Trivy 0.71.2 · TruffleHog 3.95.6 · OSV-Scanner 2.4.0 · config-audit (bundled) · mcp-exfil-scan (bundled) · skillspector 2.1.4

**APTS Audit Log:** `/tmp/css-scan-20260702T023724Z.jsonl` · 3 measured tool runs
