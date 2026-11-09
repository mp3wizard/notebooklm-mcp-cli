# Security Scan Report — 2026-11-09

Target: notebooklm-mcp-cli (post-merge of origin/main, v0.16.2)
Tools: Gitleaks, Bandit, Trivy, OSV-Scanner, TruffleHog. Semgrep started but did not finish (hung on rule fetch/timeout, stopped) — not covered this run. Opt-in tools skipped: unattended run.

| Tool | Result |
|------|--------|
| Gitleaks | 943 commits, no leaks |
| Bandit | 45 Low (0 Medium/High) — left by design |
| Semgrep | NOT COMPLETED (timeout) |
| Trivy / OSV | 0 vulnerabilities (98 packages in uv.lock) |
| TruffleHog | 0 verified, 0 unverified |

## Fixed
- Nothing needed at Medium or above. Clean merge, no conflicts.

## Remaining (by design)
- 45 Bandit Low findings.
