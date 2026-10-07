# Security scan report — 2026-10-07

Post-merge of `origin/main` (v0.15.4, 16 commits) into the fork.

| Tool | Result |
|------|--------|
| Gitleaks (896 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, 98 packages) | 0 issues |
| Trivy (`uv.lock`, vuln + secret) | 0 vulnerabilities |
| Bandit (`src`) | 44 Low, 0 Medium, 0 High (by severity) |
| Semgrep (p/python + p/secrets, files touched by merge) | 0 findings |

## Fixes
None needed (no Medium or above). Two merge conflicts resolved by hand:
- `mcp/tools/auth.py`: took upstream's headless-failure reporting, kept local SEC-007 debug log.
- `services/chat.py`: took upstream's async inflight limit; empty-notebook check now lives in upstream's source resolver.

## Left by design
44 Bandit Low (subprocess calls with fixed argument lists).

## Coverage gaps
TruffleHog and full-repo Semgrep skipped (unattended time limit). Targeted pytest (chat, MCP chat, auth studio failures, auth health): 121 passed; full suite not run.
