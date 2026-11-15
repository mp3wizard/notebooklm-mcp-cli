# Security Scan Report — 2026-11-15

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.5)  **Git HEAD:** 7534315 (pre-commit)
**Tools:** Gitleaks, Bandit, Semgrep (p/python, p/secrets, run on `src`), Trivy, OSV-Scanner

## Findings
| Severity | Tool | Finding | Status |
|---|---|---|---|
| none | OSV-Scanner / Trivy | 98 packages in uv.lock, 0 vulnerabilities | - |
| Low | Bandit | 45 subprocess-related (B404/B603/B607 etc.) | Left by design |
| none | Gitleaks | 957 commits, no leaks | - |
| none | Semgrep | 187 rules, 141 files, 0 findings | - |

## Fix
None needed. Merge brought only the `.google.com` cookie-preference fix (#408, #409) in `utils/browser.py`.

## Coverage notes
TruffleHog, CodeQL, mcps-audit, mcp-scan (opt-in), skill/exfil/skillspector audits not run (unattended run). Tests not re-run.
