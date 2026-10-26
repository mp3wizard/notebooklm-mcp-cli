# Security scan report — 2026-10-26

Post-merge of `origin/main` (3 commits, v0.15.8: #378 Windows Store config path, #379 negative session IDs, #380 signed-out landing page detection, #381 stale root-mirror rejection). Clean merge, no conflicts.

| Tool | Result |
|------|--------|
| Gitleaks (916 commits) | 0 leaks |
| OSV-Scanner (`uv.lock`, before fix) | 7 vulns: certifi 9.1 (Critical), filelock 7.1 (High), fastmcp 6.8, opentelemetry-api 5.3 (Medium), filelock 3.3 / 2.5 (Low) |
| OSV-Scanner (after fix) | 0 issues |
| Trivy 0.75.0 (`fs`, before fix) | same set as OSV (certifi, fastmcp, filelock, opentelemetry-api) |
| Bandit (`src`) | 45 Low, 0 Medium, 0 High |
| Semgrep (p/python + p/secrets, `src`) | 0 findings |
| TruffleHog (filesystem `src`) | 0 verified, 0 unverified |

## Fixes
- `uv lock --upgrade-package`: certifi 2026.2.25 → 2026.10.23, fastmcp / fastmcp-slim 3.4.7 → 3.4.11, filelock 4.0.6 → 4.2.4, opentelemetry-api 1.41.0 → 1.45.1.
- Merge defect: fork's `cli/commands/setup.py` lacked `import re` (needed by the new upstream Windows Store resolver) → NameError on import; added the import. Full suite: 2509 passed.

## Left by design
45 Bandit Low (B110, B603, B607, B404, B101, B105, B106, B112). The two Low filelock advisories were fixed by the same bump.

## Coverage gaps
mcp-scan (opt-in), CodeQL, Claude-config/skill scripts not run (unattended). Semgrep p/owasp-top-ten not run.
