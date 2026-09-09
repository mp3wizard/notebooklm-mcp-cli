# Security Scan Report — 2026-09-09

**Target:** `notebooklm-mcp-cli` (post-merge origin/main → v0.11.1)
**Git HEAD:** `0f1a8fb` (merge commit)
**Trigger:** Scheduled daily upstream-sync task, merged 3 new upstream commits (v0.11.1 security release + docs)
**Tools:** Gitleaks, Bandit, Semgrep (OWASP/Python/secrets), Trivy, TruffleHog, OSV-Scanner, mcps-audit, config-audit, skill-audit

## Merged from upstream

- **`4e63bf5` fix(security): validate pipeline names to prevent path traversal** ([GHSA-596g-p98x-c7hw](https://github.com/jacob-bd/gemini-notebook-mcp-cli/security/advisories/GHSA-596g-p98x-c7hw)) — `_load_pipeline` (MCP `pipeline` tool) and `pipeline_create` (CLI) interpolated a caller-supplied pipeline name straight into a filesystem path. A name containing `..` or an absolute path escaped the pipelines directory — on read, a crafted name could load and execute any `.yaml` on disk as a pipeline (bounded to whitelisted actions, including `notebook_delete`); on write, the CLI could write outside the directory. Names are now validated as identifiers (`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`) at both entry points. Reported by **@Naor-Peretz**.
- `7acf725` release: prepare v0.11.1 (version bump + CHANGELOG)
- `0ec1f85` docs: credit @Naor-Peretz

## Merge conflict resolution

`pyproject.toml` and `uv.lock` conflicted. Kept the local, stricter `fastmcp>=3.2.0,<4.0` pin (CVE-2026-32871 SSRF/path-traversal fix) over origin's looser `fastmcp>=2.0.0,<5.0`; regenerated `uv.lock` against the merged `pyproject.toml`.

## Findings

| Severity | Count | Status |
|---|---|---|
| Critical/Very High | 0 confirmed (10 CRITICAL from mcps-audit — false positive, see below) | — |
| High | 2 | ✅ Fixed |
| Medium | 1 | ✅ Fixed |
| Low | ~2459 (Bandit `B101` assert-in-tests) | Not fixed (declined by user for this run) |

### Fixed

- **`cryptography` 49.0.0 → 50.0.1** (High, CVE-2026-69247 / PYSEC-2026-3552 — PKCS#7 EnvelopedData decryption Bleichenbacher oracle via distinguishable errors) — `uv lock --upgrade-package cryptography`
- **`click` 8.3.2 → 8.5.0** (High, PYSEC-2026-2132) — `uv lock --upgrade-package click`
- **`pydantic-settings` 2.13.1 → 2.15.0** (Medium, [GHSA-4xgf-cpjx-pc3j](https://github.com/advisories/GHSA-4xgf-cpjx-pc3j) — `NestedSecretsSettingsSource` follows symlinks outside `secrets_dir`) — `uv lock --upgrade-package pydantic-settings`

All three vulnerabilities were introduced transitively when `uv.lock` was regenerated from origin's lock state during merge (not new commits from origin itself). Re-verified clean with `osv-scanner scan -L uv.lock` (0 issues) and `trivy fs` after `uv sync`. Full test suite re-run post-upgrade: **1580 passed, 38 skipped, 0 failed**.

### Confirmed false positives (not fixed — no code change needed)

- **TruffleHog** (3 unverified) — example URIs `https://foo.com:123,foo%3Abar@bar.com` in old `docs/security-scan-report-2026-08-*.md` files; 0 verified secrets, DNS lookups fail as expected for placeholder hosts.
- **config-audit** (Medium × 6) — `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/lowercase `claude.md` flagged for "credentials file access" / "cookie access" / "skip verification" — these are the project's own authentication documentation (how `nlm login` and cookie-based auth work), not instructions directing an agent to exfiltrate or bypass checks.
- **skill-audit** (`src/notebooklm_tools/data/SKILL.md`, risk 75/100, CRITICAL verdict) — "credential access" hit is the doc's own `nlm login` / cookie-freshness explanation; "Silent action instruction" hit is UX guidance to skip *clarifying intake questions* for Studio artifact creation, not to skip the `studio_create(confirm=True)` safety gate, which the skill explicitly keeps.
- **mcps-audit** (574 findings, risk 100/100 FAIL) — unchanged from the 2026-09-07 scan; all in `scripts/*.py` (dev-only Chrome DevTools Protocol debug tooling with inline JS strings, not packaged) or RPC constant names containing `DELETE`/`Label`. None of the flagged files were touched by this merge.

## Coverage gaps

- **`mcp-exfil-scan.sh` skipped** — bundled-script SHA256 checksum mismatch (2nd consecutive run). The scanner plugin needs reinstalling/verifying before the next scheduled run; running a script with a mismatched checksum was refused per the skill's tamper-evidence rule.
- Bandit's first pass accidentally covered `.venv/` (825k LOC, 19 "High" hits all in third-party packages) — re-run scoped to `src/` + `tests/` only via `-x "*/.venv/*"`, which returned 0 High/Medium.
- Semgrep secrets config skipped 1 file >300KB: `mcps-audit-report.pdf` (binary report artifact, not source).
- CodeQL: N/A — no `codeql.yml` workflow in this repo.
- mcp-scan / skillspector LLM-mode: skipped — opt-in, no user present to consent (unattended scheduled run).

## Low/Info remaining (deferred)

- ~2459 Bandit `B101` (`assert_used`) findings, entirely in `tests/*.py` — standard pytest assertion usage, not a runtime risk. User declined to fix in this run.
