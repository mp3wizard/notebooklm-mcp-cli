# Security Scan Report — 2026-10-28

Target: notebooklm-mcp-cli (post-merge of origin/main, CI action bumps after v0.15.8)
Tools: Gitleaks, Bandit, Semgrep (p/python, p/secrets), Trivy, OSV-Scanner. Opt-in tools (mcp-scan, Jev, LLM modes) skipped: unattended run.

| Tool | Result |
|------|--------|
| Gitleaks | 920 commits, no leaks |
| Bandit | 45 Low (0 Medium/High) — left by design |
| Semgrep | 0 findings |
| Trivy / OSV | authlib 1.8.0 (1 Critical, 2 High, 4 Medium), dnspython 2.8.0 (1 High) |

## Fixed
- `uv lock --upgrade-package authlib --upgrade-package dnspython`: authlib → 1.9.1, dnspython → 2.9.0. OSV rescan: no issues. pytest: 2509 passed.

## Remaining (by design)
- 45 Bandit Low findings.
