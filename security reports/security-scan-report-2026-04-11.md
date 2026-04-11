# Security Assessment Report

**Target:** `notebooklm-mcp-cli`
**Location:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scan Date:** 2026-04-11
**Version scanned:** v0.5.20 (post-merge — commit `b8f1f21`)
**Analyst:** Claude Security Review (claude-sonnet-4-6)
**Report Version:** 1.0 — Automated Scan

---

## Table of Contents

1. [Pre-flight Check](#pre-flight-check)
2. [Automated Scan Results](#automated-scan-results)
3. [Vulnerabilities Found & Fixed](#vulnerabilities-found--fixed)
4. [Remaining Low/Info Findings](#remaining-lowinfo-findings)
5. [Remediation Summary](#remediation-summary)

---

## Pre-flight Check

```
OK  bandit 1.9.4
OK  semgrep 1.157.0
OK  trivy 0.69.3  (safe — compromised range: 0.69.4–0.69.6)
OK  trufflehog 3.94.2
OK  gitleaks 8.30.1
OK  osv-scanner 2.3.5
OK  gh (CodeQL — no codeql.yml workflow found, skipped)
OK  npx (mcps-audit — no .mcp.json in project, skipped)
OK  uvx (mcp-scan — opt-in only, not requested)
OK  config-audit.py (bundled)
OK  skill-audit.sh (bundled)
OK  mcp-exfil-scan.sh (bundled)
```

---

## Automated Scan Results

### Gitleaks — Secrets in git history + filesystem

**Exit code:** 0

```
433 commits scanned.
scanned ~8477238 bytes (8.48 MB) in 1.08s
no leaks found
```

**Result:** Zero secrets detected in git history or working tree.

---

### TruffleHog — Secrets with live API verification

**Exit code:** 0

```
chunks: 6193, bytes: 8695813
verified_secrets: 0, unverified_secrets: 0
scan_duration: 879ms
```

**Result:** Zero verified or unverified secrets found.

---

### Bandit — Python SAST (src/ only)

**Exit code:** 1 (Low issues only)

```
Total lines of code: ~27806 (src/)
Total issues (by severity):
  High:   0
  Medium: 0
  Low:    48
```

All Low findings are expected subprocess patterns (B603, B404, B607) in `setup.py`, `cdp.py`, `doctor.py`, and `wsl.py` — all use list args, not shell=True. No Medium or High findings in project source code.

---

### Semgrep — SAST (OWASP Top 10 + Python + Secrets)

**Exit code:** 0 for all three configs

| Config | Rules Run | Findings |
|--------|-----------|----------|
| p/owasp-top-ten | 153 | 0 |
| p/python | 151 | 0 |
| p/secrets | 37 | 0 |

**Result:** Clean across all rulesets.

---

### Trivy — Dependency vulnerabilities (uv.lock)

**Pre-fix:**

```
Library   Vulnerability    Severity  Version   Fixed
pygments  CVE-2026-4539    LOW       2.19.2    2.20.0
requests  CVE-2026-25645   MEDIUM    2.32.5    2.33.0
```

**Post-fix:** No findings.

---

### OSV-Scanner — SCA via OSV.dev (uv.lock)

**Pre-fix:**

```
Package         GHSA                    CVSS  Fixed Version
jaraco-context  GHSA-58pv-8j8x-9vj2    8.6   6.1.0   (HIGH)
requests        GHSA-gc5v-m9x4-r6x2    4.4   2.33.0  (MEDIUM)
pygments        GHSA-5239-wwwm-4pmq    3.3   2.20.0  (LOW)
```

**Post-fix:**

```
No issues found
```

---

### Config Audit — Claude Code configuration

**Exit code:** 0

**21 findings total** — all confirmed false positives or out-of-scope:

- **5 CRITICAL** — security-scanner skill scripts detected scanning for base64/exfil patterns. These scripts *look for* these patterns as part of their analysis, not performing them.
- **5 HIGH** — `validate-bash.sh` in plugin-dev contains example dangerous commands (mkfs, dd) as test cases for validation logic — by design.
- **9 MEDIUM** — `CLAUDE.md` references to cookies/credentials are documentation of auth process, not exfiltration. Playwright-cli skill references password/cookie fields as part of browser automation scope.
- **2 LOW** — Hooks configuration found (expected, legitimate).

**Result:** No actionable issues in project codebase.

---

### Skill Audit — notebooklm-cli.skill + SKILL.md

| Skill | Risk Score | Verdict |
|-------|-----------|---------|
| `notebooklm-cli.skill` | 0/100 | LOW RISK — APPROVE |
| `src/notebooklm_tools/data/SKILL.md` | 35/100 | MEDIUM RISK — APPROVE WITH CAUTION |

SKILL.md score of 35 reflects presence of example URLs and bash code blocks (documentation). No dangerous patterns or prompt injection detected.

---

### MCP Exfil Scan

**9 findings** — all confirmed false positives:

- 2 CRITICAL: `security-scanner/mcp-exfil-scan.sh` and `skill-security-auditor/SKILL.md` flagged for scanning for exfil patterns (they look for exfil, they don't perform it)
- 3 HIGH: `skill-security-auditor` has Read+WebFetch+Bash by design (security scanning requires these tools)
- 4 MEDIUM: Source attribution warnings for `playwright-cli`, `pyright`, `vtsls` skills

**Result:** No actionable issues for notebooklm-mcp-cli project.

---

## Vulnerabilities Found & Fixed

| Severity | Package | GHSA / CVE | CVSS | Version Before | Version After | Fix Method |
|----------|---------|-----------|------|----------------|--------------|------------|
| **HIGH** | `jaraco-context` | GHSA-58pv-8j8x-9vj2 | 8.6 | 6.0.2 | **6.1.2** | `uv lock --upgrade-package jaraco-context` |
| **MEDIUM** | `requests` | GHSA-gc5v-m9x4-r6x2 / CVE-2026-25645 | 4.4 | 2.32.5 | **2.33.1** | `uv lock --upgrade-package requests` |
| **LOW** | `pygments` | GHSA-5239-wwwm-4pmq / CVE-2026-4539 | 3.3 | 2.19.2 | **2.20.0** | `uv lock --upgrade-package pygments` |

All 3 vulnerabilities resolved. `osv-scanner scan source -r .` returns **No issues found**.

---

## Remaining Low/Info Findings

| Finding | Tool | Disposition |
|---------|------|-------------|
| B603/B404/B607 subprocess (48x) | Bandit | False positives — all use list args, not shell=True. No user-controlled input. |
| B107/B105 hardcoded password strings | Bandit | False positives — status message strings containing the word "token", not passwords. |
| Config audit CRITICAL/HIGH/MEDIUM | config-audit | False positives — security-scanner scripts and CLAUDE.md documentation. |

---

## Remediation Summary

**Scan context:** Post-merge v0.5.18–v0.5.20 from upstream origin

**Actions taken:**
1. Merged origin/main (13 commits — WSL2 auth, thread-safety, research fixes, verb parity)
2. Resolved 4 merge conflicts (pyproject.toml, base.py, cdp.py, uv.lock)
3. Upgraded `jaraco-context` 6.0.2 → 6.1.2 (HIGH)
4. Upgraded `requests` 2.32.5 → 2.33.1 (MEDIUM)
5. Upgraded `pygments` 2.19.2 → 2.20.0 (LOW)
6. Regenerated uv.lock

**Final status:** 0 open vulnerabilities. Codebase clean.
