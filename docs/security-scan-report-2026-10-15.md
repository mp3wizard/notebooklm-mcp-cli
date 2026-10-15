# Security scan report — 2026-10-15

Post-merge of `origin/main` (v0.15.5, 6 commits) into the fork. Clean merge, no conflicts.

| Tool | Result |
|------|--------|
| Gitleaks (903 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, 98 packages) | 0 issues |
| Trivy (`uv.lock`, vuln + secret) | 0 vulnerabilities |
| Bandit (`src`) | 45 Low, 0 Medium, 0 High (by severity) |
| Semgrep (p/owasp-top-ten + p/python + p/secrets, `src`, 137 files) | 0 findings |
| TruffleHog (git history, unverified mode) | 0 verified; 13 unverified URI hits, all in old `docs/security-scan-report-*.md` (URL examples, not secrets) |

## Fixes
None needed (no Medium or above).

## Left by design
45 Bandit Low (subprocess calls with fixed argument lists, asserts, try/except/pass).

## Coverage gaps
mcp-scan (opt-in, external), CodeQL and the Claude-config/skill scripts not run (unattended). Full pytest suite not run.
