# Security scan report — 2026-10-16

Post-merge of `origin/main` (4 commits after v0.15.5: #374, #375, #376 auth fixes + changelog) into the fork. Clean merge, no conflicts.

| Tool | Result |
|------|--------|
| Gitleaks (908 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, 98 packages) | 0 issues |
| Trivy (`uv.lock`) | 0 vulnerabilities |
| Bandit (`src`) | 45 Low, 0 Medium, 0 High (by severity) |
| Semgrep (p/owasp-top-ten + p/python + p/secrets, `src`) | 0 findings |
| TruffleHog (git history, verified only) | 0 verified, 0 unverified |

## Fixes
None needed (no Medium or above).

## Left by design
45 Bandit Low (subprocess calls with fixed argument lists, asserts, try/except/pass).

## Coverage gaps
mcp-scan (opt-in, external), CodeQL and the Claude-config/skill scripts not run (unattended). Full pytest suite not run.
