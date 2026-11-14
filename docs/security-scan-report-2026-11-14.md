# Security Scan Report — 2026-11-14

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.4)  **Git HEAD:** 3a9527e (pre-commit)
**Tools:** Gitleaks, Bandit, Semgrep (p/python, p/owasp-top-ten, p/secrets, run on `src`), Trivy, TruffleHog (verified only), OSV-Scanner

## Findings
| Severity | Tool | Finding | Status |
|---|---|---|---|
| High (CVSS 7.5) | OSV/Trivy | dnspython 2.9.0, GHSA-vvf4-9x63-8xvv, excessive memory/CPU | Fixed: 2.9.2 |
| Medium (5.3) | OSV/Trivy | opentelemetry-api 1.45.1, GHSA-mf5v-w3w3-f6cg, quadratic traceparent parsing | Fixed: 1.45.2 |
| Low | Bandit | 45 subprocess-related (B404/B603/B607 etc.) | Left by design |
| none | Gitleaks | 953 commits, no leaks | - |
| none | TruffleHog | 0 verified, 0 unverified secrets | - |
| none | Semgrep | 0 findings | - |

## Fix
`uv lock --upgrade-package dnspython --upgrade-package opentelemetry-api` + `uv sync`. OSV rescan: no issues. Tests: 2667 passed, 39 skipped.

## Coverage notes
CodeQL, mcps-audit, mcp-scan (opt-in), skill/exfil/skillspector audits not run (unattended run).
