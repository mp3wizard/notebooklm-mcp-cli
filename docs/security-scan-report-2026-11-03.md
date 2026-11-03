# Security Scan Report — 2026-11-03

Target: notebooklm-mcp-cli (post-merge of origin/main, v0.15.9)
Tools: Gitleaks, Bandit, Semgrep (owasp-top-ten, p/python, p/secrets), Trivy 0.76.1, OSV-Scanner. Opt-in tools (mcp-scan, Jev, LLM modes) skipped: unattended run.

| Tool | Result |
|------|--------|
| Gitleaks | 924 commits, no leaks |
| Bandit | 45 Low (0 Medium/High) — left by design |
| Semgrep | 0 findings |
| Trivy / OSV | joserfc 1.7.5 (1 Medium, GHSA-9pg5-8c7x-5hfx, DoS via JWS deserialization) |

## Fixed
- `uv lock --upgrade-package joserfc`: joserfc → 1.7.7. OSV rescan: no issues. pytest: 2514 passed, 39 skipped.

## Remaining (by design)
- 45 Bandit Low findings.
