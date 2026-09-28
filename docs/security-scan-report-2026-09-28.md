# Automated Security Scan Report
**Target:** `notebooklm-mcp-cli`  **Scanned:** 2026-09-28  **Git HEAD:** `c85449b` (post-merge of origin/main v0.13.0)
**Standard:** OWASP APTS-aligned

## Coverage
| Tool | Result |
|------|--------|
| Gitleaks 8.30.1, 813 commits | no leaks |
| TruffleHog 3.97.5 | 0 verified / 8 unverified (placeholder URLs `foo.com`/`bar.com` in old docs, pre-existing) |
| Bandit 1.9.4 (`src/`, `tests`/`.venv` excluded) | 32 Low (subprocess B603/B607, fixed-argv, standard project pattern), 0 Medium, 0 High |
| Semgrep (owasp-top-ten, secrets; excl. `.venv`) | 0 findings |
| Trivy 0.74.0 (`uv.lock`) | 0 vulns, 0 secrets |
| OSV-Scanner 2.6.0 (98 packages) | No issues found |
| mcp-exfil-scan | RISK 0/100 CLEAN |
| config-audit | Findings in this repo limited to MEDIUM false-positives on `CLAUDE.md`/`AGENTS.md` (heuristic matches on legitimate auth/cookie troubleshooting docs); CRITICAL/HIGH items in the report are all in unrelated global `~/.claude` skills/plugins, out of scope for this target |
| skill-audit (`data/SKILL.md`) | Risk 75/100 — driven by heuristic false positives: "credentials" match is the documented `nlm login` flow, "silent action" match is `Silently infer` (internal reasoning shortcut before a compact confirmation, not a hidden action — `studio_create` still requires `confirm=True`) |
| mcps-audit v1.0.0 | 620 findings (10 Critical / 133 High / 473 Medium / 4 Low), Risk 100/100 — reviewed and dismissed as noise: flags every `page.evaluate`-style JS string in local CDP debug scripts (`scripts/inject_cookies_and_inspect.py`, `scripts/inspect_upload_dom.py`) as "Dangerous execution" and flags absence of a logging framework in single-purpose scripts as MEDIUM in nearly every file |
| CodeQL / mcp-scan / skillspector | not run (N/A or opt-in) |

## Merge
Merged 27 upstream commits (v0.12.1 fixes + v0.13.0 guided setup wizard) at `c85449b`. Conflicts in `CLAUDE.md`, `pyproject.toml`, `src/notebooklm_tools/cli/commands/setup.py`, `uv.lock` resolved in favor of origin's config-file-based status checks and dynamic binary-path resolution, keeping local's newer pinned dev dependencies. Dead `_cli_output_contains_mcp` helper removed post-merge; ruff clean.

## Fixes
None required — no Very High / High / Medium findings in project-owned code.

## Remaining (Low/Info, left by design)
- 32 Bandit Low subprocess findings in `src/` (fixed-argv calls, no shell).
- 8 TruffleHog unverified placeholder-URL matches in historical scan-report docs.
- config-audit MEDIUM false positives on this repo's own `CLAUDE.md`/`AGENTS.md` auth docs.
- skill-audit and mcps-audit heuristic false positives noted above — no code change indicated.

## Verification
Full non-e2e suite: 1,898 passed, 39 skipped. Ruff lint and format clean. `uv lock` resolves cleanly (98 packages).
