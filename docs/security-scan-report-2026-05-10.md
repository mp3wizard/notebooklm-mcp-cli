# Security Scan Report — 2026-05-10 (post-merge v0.6.6 + cited-research-import)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD (post-merge):** `13303cd` (merge of `origin/main` @ `bb8ea48`)
**Trigger:** Daily upstream sync — merged 9 commits from `origin/main` (v0.6.4 → v0.6.6 + PR #188)

## Upstream changes merged

| Commit | Type | Summary |
|--------|------|---------|
| `1f630fe` | Fix (auth) | resolve premature cookie extraction race condition (Issue #181) — v0.6.5 |
| `c328a9d` | Docs | add Google AI Ultra to tested tiers (PR #184) |
| `d3c10a6` | Fix (errors) | decode `UserDisplayableError` payload for code 8 (RESOURCE_EXHAUSTED, Issue #182) |
| `677eec4` | Fix (video) | point users to `--focus` when cinematic rejects `--style`/`--style-prompt` |
| `09a813d` | Fix (video) | validate cinematic flags before API calls; deduplicate hint |
| `1831105` | Feature (video) | map `--style-prompt` to `custom_instructions` for cinematic format (Issue #183) |
| `4e047d8` | Chore | release v0.6.6 |
| `9c86102` | Feature | import cited research sources (PR #188) |
| `bb8ea48` | Merge | PR #188 |

## Tools run

| Tool | Version | Result |
|------|---------|--------|
| Gitleaks | 8.30.1 | 0 leaks (521 commits, 9.19 MB) |
| Bandit | 1.9.4 | 2 Low (try/except/pass retry loops; 55 `# nosec` skipped); 22,679 LOC |
| Semgrep — OWASP Top 10 | 1.157.0 | 0 findings (153 rules / 101 files) |
| Semgrep — Python | 1.157.0 | 0 findings (151 rules / 101 files) |
| Semgrep — Secrets | 1.157.0 | 0 findings (38 rules / 142 files) |
| Trivy fs | 0.69.3 | **1 HIGH** (uv.lock — 88 pkgs) |
| TruffleHog (verified) | 3.94.2 | 0 verified, 0 unverified (7,149 chunks) |
| OSV-Scanner | 2.3.5 | **1 HIGH** (uv.lock — 88 pkgs; matches Trivy) |
| config-audit | bundled | 4 Medium (CLAUDE.md doc-text false positives) + Low informational |
| skill-audit | bundled | risk 35/100 (Medium — bash complexity in `data/SKILL.md`) |
| mcp-exfil-scan | bundled | findings out-of-scope (scanned global `~/.claude/skills/`, not this repo) |

## Findings by severity

| Severity | Count |
|----------|------:|
| Very High | 0 |
| High | 1 (fixed) |
| Medium | 4 (false positive — doc references in `CLAUDE.md`) |
| Low | 2 (Bandit B110, retry loops) |
| Info | n/a |

## High severity — fixed

### CVE-2026-42561 — `python-multipart` 0.0.26 → 0.0.28
- **Source:** Trivy + OSV-Scanner (GHSA-pp6c-gr5w-3c5g, CVSS 7.5)
- **Title:** Denial of Service via unbounded multipart part headers
- **Fix applied:**
  ```bash
  uv lock --upgrade-package python-multipart
  uv sync
  ```
  Result: `python-multipart 0.0.26 → 0.0.28`
- **Re-scan:** OSV-Scanner clean (`No issues found`)

## Medium / Low — not fixed (rationale)

- **4× config-audit Medium** on `CLAUDE.md` — substring matches on words like "cookie" and "credential" in **documentation prose** describing the auth flow. No actual credential or secret material; left as-is.
- **2× Bandit B110 (Low)** at `src/notebooklm_tools/utils/cdp.py:1066, 1284` — `try/except/pass` inside CDP polling/retry loops. Pattern is intentional (silent retry), low-confidence vulnerability per Bandit; not introduced by this merge. Left as-is.
- **mcp-exfil-scan findings** — scanner traversed `~/.claude/skills/` (out-of-scope per APTS Scope Enforcement). Not findings against this repo.

## Outcome

- **Risk posture before fix:** 1 HIGH (transitive dep CVE)
- **Risk posture after fix:** Clean
- **Files changed by Phase 3c:** `uv.lock` (python-multipart 0.0.26 → 0.0.28; project version bumped 0.6.2 → 0.6.6 by lock refresh)
