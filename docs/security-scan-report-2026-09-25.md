# Automated Security Scan Report
**Target:** `notebooklm-mcp-cli`  **Scanned:** 2026-09-25  **Git HEAD:** `43f1f5f` (post-merge of origin/main v0.12.0)
**Standard:** OWASP APTS-aligned

## Coverage
| Tool | Result |
|------|--------|
| Gitleaks 787 commits | no leaks |
| TruffleHog 3.97.5 (verified) | 0 verified / 0 unverified |
| Bandit 1.9.4 (`src/`) | 17 Low (B603/B607/etc. subprocess, all pre-existing pattern), 0 Medium, 0 High |
| Semgrep (owasp-top-ten, python, secrets; `src/`) | 0 findings |
| Trivy 0.74 (`uv.lock`) | 0 vulns, 0 secrets |
| OSV-Scanner (90 packages) | No issues found |
| mcp-exfil-scan | RISK 0/100 CLEAN |
| config-audit | LOW only (hook config presence) |
| CodeQL / mcp-scan / skillspector / mcps-audit | not run (N/A or opt-in) |

## Fixes
None required — no Very High / High / Medium findings.

## Remaining (Low/Info, left by design)
- 17 Bandit Low subprocess findings in `src/` (fixed-argv calls, no shell).
- config-audit LOW: hooks presence.

## Verification
Full non-e2e suite: 1,747 passed, 38 skipped.
