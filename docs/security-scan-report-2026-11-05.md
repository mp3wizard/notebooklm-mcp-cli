# Security Scan Report — 2026-11-05

Target: notebooklm-mcp-cli (post-merge of origin/main, v0.16.0)
Tools: Gitleaks, Bandit, Semgrep (owasp-top-ten, p/python, p/secrets), Trivy, OSV-Scanner, TruffleHog. Opt-in tools (mcp-scan, Jev, LLM modes) skipped: unattended run.

| Tool | Result |
|------|--------|
| Gitleaks | 937 commits, no leaks |
| Bandit | 45 Low (0 Medium/High) — left by design |
| Semgrep | 0 findings |
| Trivy / OSV | 0 vulnerabilities (98 packages in uv.lock) |
| TruffleHog | 0 verified; 8 unverified URI hits in old `docs/security-scan-report-*.md` history — Info, left |

## Fixed
- Nothing needed at Medium or above. Merge conflict in `core/base.py` resolved toward upstream's payload-free RPC debug logging (#390). pytest: 2608 passed, 39 skipped.

## Remaining (by design)
- 45 Bandit Low findings; 8 unverified TruffleHog URI hits in historical reports.
