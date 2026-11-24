# Security Scan Report — 2026-11-24

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.7)  **Git HEAD:** ce220f4 (pre-commit)
**Tools:** Gitleaks, Bandit, Semgrep (p/owasp-top-ten, p/python, p/secrets, on `src`), Trivy, OSV-Scanner, TruffleHog (git, verified-only), config-audit, mcp-exfil-scan

## Findings
| Severity | Tool | Finding | Status |
|---|---|---|---|
| none | OSV-Scanner / Trivy | 98 packages in uv.lock, 0 vulnerabilities | - |
| Low | Bandit | 45 (0 Medium, 0 High) | Left by design |
| none | Gitleaks | 968 commits, no leaks | - |
| none | Semgrep | 3 configs, 0 findings | - |
| none | TruffleHog | 0 verified, 0 unverified secrets | - |
| none | mcp-exfil-scan | risk score 0/100, CLEAN | - |
| Low | config-audit | Hooks configuration present (informational, plugin hooks) | Left by design |

## Fix
None needed. Merge brought cookie-file parsing fixes (#411, #412) in `utils/browser.py`.

## Coverage notes
CodeQL, mcps-audit, mcp-scan (opt-in), skillspector, Jev triage not run (unattended run). Tests not re-run.
