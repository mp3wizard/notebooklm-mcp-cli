# Security scan report — 2026-10-06

Post-merge of `origin/main` (v0.15.3 + `85a956f` usage-plan error fix) into the fork. Merge commit `cc5d46c`.

| Tool | Result |
|------|--------|
| Gitleaks (879 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, 98 packages) | 0 issues |
| Trivy (`uv.lock`, vuln + secret) | 0 vulnerabilities |
| Bandit (`src`) | 44 Low, 0 Medium, 0 High |
| Semgrep (p/python + p/secrets, 6 merge-touched files) | 0 findings |

## Fixes
None needed (no Medium or above). One merge conflict in `utils/cdp.py` resolved by hand (upstream sign-in wait loop + local SEC-007 debug logging).

## Left by design
44 Bandit Low (mostly B603/B607 subprocess calls with fixed argument lists).

## Coverage gaps
- Full-repo Semgrep and TruffleHog did not finish within the unattended time limit; Semgrep covered only the six files touched by the merge.
- Full pytest run timed out; the merge-relevant suites passed (125 tests: CDP login validation, auth check, CDP transport, sources, usage, auth health, login CLI).
