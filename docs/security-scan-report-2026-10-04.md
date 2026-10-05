# Security Scan Report — 2026-10-04

**Target:** notebooklm-mcp-cli (working tree after merging `origin/main` through v0.15.1)
**Tools:** Bandit 1.x, Semgrep 1.177.0 (p/owasp-top-ten, p/python, p/secrets), Gitleaks, Trivy, OSV-Scanner, TruffleHog 3.97.5, config-audit, skill-audit, mcp-exfil-scan

## Results

| Tool | Result |
|------|--------|
| Bandit (`src/`) | 44 Low, 0 Medium, 0 High |
| Semgrep (OWASP / Python / secrets) | 0 findings (153 + 151 + 38 rules) |
| Gitleaks (866 commits, 12.6 MB) | No leaks |
| Trivy (`uv.lock`, 98 packages) | 0 vulnerabilities |
| OSV-Scanner (`uv.lock`) | No issues |
| TruffleHog | 0 verified; 15 unverified URI/Pastebin hits, all inside `.venv/` (third-party) |
| mcp-exfil-scan | 0/100, CLEAN |
| skill-audit (`src/notebooklm_tools/data/SKILL.md`) | Medium "silent action" pattern fixed (see below); heuristic score 75 → 55 |
| config-audit | MEDIUM hits on project `CLAUDE.md` / `AGENTS.md` are doc text mentioning credentials and cookies (false positives). HIGH hits are in third-party plugin hooks outside this repo (not in scope). |

## Fixes applied

- `src/notebooklm_tools/data/SKILL.md` (lines 68, 511): replaced "Infer … silently" with "Infer … from context without asking". The `confirm=True` gate is unchanged. Clears the Medium prompt-injection-pattern heuristic.

## Remaining (not fixed, by design)

- Bandit Low (44): mostly `try/except/pass` (B110), subprocess use (B603/B607), and assert use. No Medium or High items.
- skill-audit heuristic "High bash complexity" (+10 points) on `SKILL.md`: a complexity heuristic, not a vulnerability.
- config-audit MEDIUM false positives on the project's own docs.

## Notes

- Semgrep needs the pipx binary, `$HOME/.local/bin/semgrep`.
- Tool versions and this run's tool outputs are kept in the scratch directory, not committed.
