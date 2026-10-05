# Security Scan Report — 2026-10-05

**Target:** notebooklm-mcp-cli (working tree after merging `origin/main` through v0.15.2, merge commit `f7d031a`)
**Tools:** Bandit 1.9.4, Semgrep (p/owasp-top-ten, p/python, p/secrets), Gitleaks, Trivy, OSV-Scanner, TruffleHog 3.97.5

## Results

| Tool | Result |
|------|--------|
| Bandit (`src/`) | 44 Low, 0 Medium, 0 High |
| Semgrep (191 rules, 126 files) | 0 findings |
| Gitleaks (871 commits, 12.6 MB) | No leaks |
| Trivy (`uv.lock`) | 0 vulnerabilities |
| OSV-Scanner (`uv.lock`, 98 packages) | No issues |
| TruffleHog (git history) | 0 verified, 0 unverified |
| Tests | 2,362 passed, 39 skipped |

## Fixes applied

None needed. Merge applied cleanly (no conflicts); no Medium+ findings.

## Remaining (not fixed, by design)

- Bandit Low (44): B110 try/except/pass (16), B603 subprocess (14), B404 (4), B607 (4), B101 (2), B105 (2), B106 (1), B112 (1).

## Not run

config-audit, skill-audit, mcp-exfil-scan, CodeQL, mcps-audit, mcp-scan, skillspector (not required by the workflow; skill/MCP files unchanged in substance).
