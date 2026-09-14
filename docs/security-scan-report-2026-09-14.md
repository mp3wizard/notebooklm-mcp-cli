# Security Scan Report — 2026-09-14

**Target:** `notebooklm-mcp-cli` (post-merge origin/main → v0.11.4)
**Git HEAD:** `6a3c5a5` (first merge, to v0.11.3) then a second fast-forward-style merge to v0.11.4 (no conflicts)
**Trigger:** Scheduled daily upstream-sync task, merged 5 new upstream commits
**Tools:** Gitleaks, Bandit, Semgrep (OWASP/Python/secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit

## Merged from upstream

- `1a30420` feat: report remaining plan usage via `nlm usage`/`usage_get` (PR #327, @WAOmaster)
- `2506f3f` docs: document plan usage checks in skill
- `adfa44d` chore: prepare 0.11.3 release
- `bbfe02f` fix: support isolated usage checks for named profiles (PR #328, @insane66613) — `--profile <name>` now takes precedence over `NOTEBOOKLM_COOKIES`; missing profiles fail instead of silently falling back to another account
- `7f9cb1d` chore: prepare 0.11.4 release

No security fixes shipped upstream this cycle — 0.11.3/0.11.4 are a feature + correctness patch (usage metering, profile isolation).

## Merge conflict resolution

This run also had to finish a **stale merge left over from a prior interrupted run** (`MERGE_HEAD` pointed at `adfa44d`, v0.11.3). `CLAUDE.md` had two conflicts:
- **Test Structure section** — kept local's accurate directory tree; dropped origin's outdated granular MCP-tool table (superseded locally by consolidated `note`/`batch`/`tag` tools).
- **Troubleshooting section** — kept local's compact table format, folded in origin's newer usage-metering/rate-limit content (matches the `usage_get`/`nlm usage` feature already present locally).

A stray leftover `>>>>>>> origin/main` marker from the first edit pass was caught by a post-edit grep and removed before committing. The remaining v0.11.4 merge (README.md, pyproject.toml, `cli/utils.py`) auto-merged with no conflicts.

## Findings

| Severity | Count | Status |
|---|---|---|
| Critical/Very High | 0 | — |
| High | 0 | — |
| Medium | 0 confirmed (9 raw flags — all false positive, see below) | Not fixed (no code change needed) |
| Low | 1 confirmed false positive (Bandit `B108`) + ~2503 `B101` assert-in-tests | Not fixed (declined by design) |

### Confirmed false positives (not fixed — no code change needed)

- **Bandit** (`test_usage_profiles.py:39`, Medium `B108` hardcoded_tmp_directory) — `"/tmp/account"` is a parametrized *input value being tested for rejection* (invalid profile name), not a temp-file path the code creates.
- **TruffleHog** (5 unverified) — example URIs `https://foo.com:123,foo%3Abar@bar.com` in old `docs/security-scan-report-2026-08-*.md`/`2026-09-*.md` files; 0 verified secrets, DNS lookups fail as expected for placeholder hosts.
- **config-audit** (Medium × 8) — `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` flagged for "credentials file access" / "cookie access" — the project's own authentication documentation, unchanged pattern from prior scans.
- **skill-audit** (`src/notebooklm_tools/data/SKILL.md`, risk 75/100, CRITICAL verdict) — same recurring false positive as prior scans: "credential access" is the `nlm login`/cookie doc; "Silent action instruction" is UX guidance to skip *clarifying intake questions* for Studio, not the `studio_create(confirm=True)` safety gate (explicitly kept per the skill text itself, line 69).

## Coverage gaps

- **`mcp-exfil-scan.sh` skipped** — bundled-script SHA256 checksum mismatch (recurring — same gap as the 2026-09-07 and 2026-09-09 runs). The `claude-code-security-plugins` install needs reinstalling/verifying; not attempted here per the scheduled task's "no exploring alternatives" rule.
- Semgrep secrets config skipped 1 file >300KB: `mcps-audit-report.pdf` (binary report artifact, not source).
- CodeQL: N/A — no `codeql.yml` workflow in this repo.
- mcp-scan / skillspector LLM-mode: skipped — opt-in, no user present to consent (unattended scheduled run).
- mcps-audit not re-run this cycle (unchanged surface from 2026-09-09; no MCP tool files touched by this merge).

## Low/Info remaining (deferred)

- ~2503 Bandit `B101` (`assert_used`) findings, entirely in `tests/*.py` — standard pytest assertion usage, not a runtime risk.
