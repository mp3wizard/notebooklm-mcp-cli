# Security scan report — 2026-10-18

Post-merge of `origin/main` (3 commits, v0.15.6: #377 collection edit fix, unknown-collection guard, release prep) into the fork. Clean merge, no conflicts. Code change: `core/collections.py` (+ tests, docs).

| Tool | Result |
|------|--------|
| Gitleaks (912 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, 98 packages) | 0 issues |
| Trivy 0.75.0 (`uv.lock`) | 0 vulnerabilities |
| Bandit (`src`) | 45 Low, 0 Medium, 0 High |
| Semgrep (p/owasp-top-ten + p/python + p/secrets, `src`) | 0 findings |
| TruffleHog (git, since previous merge) | 0 verified, 0 unverified |

## Fixes
None needed (no Medium or above).

## Left by design
45 Bandit Low (B110 try/except/pass ×16, B603 ×14, B607 ×4, B404 ×4, B101 ×3, B105 ×2, B106, B112).

## Coverage gaps
mcp-scan (opt-in), CodeQL, Claude-config/skill scripts not run (unattended). Full pytest suite not run.
