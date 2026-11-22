# Security Scan Report — 2026-11-22

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.6)  **Git HEAD:** 84999aa (pre-commit)
**Tools:** Gitleaks, Bandit, Semgrep (p/owasp-top-ten, p/python, p/secrets, on `src` + `tests`), Trivy, OSV-Scanner, TruffleHog (filesystem, verified-only)

## Findings
| Severity | Tool | Finding | Status |
|---|---|---|---|
| none | OSV-Scanner / Trivy | 98 packages in uv.lock, 0 vulnerabilities | - |
| Low | Bandit | 45 (B110 x16, B603 x14, B607/B404 x4 each, B101 x3, B105 x2, B106, B112) | Left by design |
| none | Gitleaks | 964 commits, no leaks | - |
| none | Semgrep | 3 configs, 133 files, 0 findings | - |
| none | TruffleHog | 0 verified, 0 unverified secrets | - |

## Fix
None needed. Merge brought the setup wizard Claude Desktop/Relay profile changes and the WSL `check_firewall_rule()` bool fix (#410).

## Coverage notes
CodeQL, mcps-audit, mcp-scan (opt-in), skill/exfil/skillspector audits not run (unattended run). Tests not re-run. Semgrep run on `src`/`tests` only.
