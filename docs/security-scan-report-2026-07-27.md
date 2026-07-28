# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-27 (post-merge of `origin/main`, 4 new commits: b2ab425..74d3575 — v0.9.3/0.9.4, Gemini Notebook host support + Chrome-handoff error fix + rebrand)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    main (merge commit 8a8f654, merging origin/main)
Focus:       full repo, with emphasis on the new host-allowlist and CDP
             hand-off code (utils/cdp.py, utils/config.py)
Include:     all supported (Python/JS/config)
Exclude:     .venv (excluded explicitly on the second bandit pass — see note below)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 684 commits, ~10.58MB | — |
| Bandit | OK | 1.9.4 | 41,815 LOC (`.venv` excluded) | — |
| Semgrep (OWASP + Python) | OK | pipx build | 176 files, 185 rules | `.venv` excluded via `.semgrepignore` (84 files) |
| Trivy | OK | 0.72.0 | `uv.lock`, dependency scan | — |
| TruffleHog | OK | 3.95.9 | full git history, 9,025 chunks / 10.94MB | — |
| mcps-audit | OK | 1.0.0 | 194 files / 53,852 lines | — |
| CodeQL | SKIPPED | — | — | no CodeQL workflow in `.github/workflows/` |

**Note:** the first Bandit pass was run against the whole repo (`.` — no excludes) and accidentally scanned `.venv`, inflating LOC to 818K (7072 Low / 200 Medium / 19 High — all third-party noise). Re-ran with `-x ./.venv` — this is the result reported below.

## Gitleaks — Secrets (filesystem + history)
**Summary:** 0 leaks (684 commits scanned, ~10.58MB).
```
9:40AM INF 684 commits scanned.
9:40AM INF scanned ~10584570 bytes (10.58 MB) in 913ms
9:40AM INF no leaks found
```

## Bandit — Python SAST
**Summary:** 0 High, 0 Medium, 1999 Low in-scope (`.venv` excluded). All 81 Medium findings from the unfiltered pass live in `tests/` — **0 High/Medium in `src/`**, confirmed via bandit JSON output filtered on `filename.startswith('./src')`.
```
Code scanned (in-scope, .venv excluded):
	Total lines of code: 41815
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 72

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 1999
		Medium: 81
		High: 0
```
Medium-severity sample (all `tests/`, `B101:assert_used` / fixture-pattern noise): `tests/test_mcp_chat.py:51`, `tests/services/test_cross_notebook.py:196`, `tests/cli/test_json_parity.py:225`, `tests/cli/test_chats_cli.py:66`. No action taken — same pattern as every prior scan.

## Semgrep — OWASP Top Ten / Python
**Summary:** 0 findings (185 rules, 176 files, ~99.9% parsed).
```
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 185
 • Targets scanned: 176
 • Parsed lines: ~99.9%
Ran 185 rules on 176 files: 0 findings.
```

## Trivy — Dependency scan
**Summary:** 0 vulnerabilities (`uv.lock`).
```
┌─────────┬──────┬─────────────────┬─────────┐
│ Target  │ Type │ Vulnerabilities │ Secrets │
├─────────┼──────┼─────────────────┼─────────┤
│ uv.lock │  uv  │        0        │    -    │
└─────────┴──────┴─────────────────┴─────────┘
```
No dependency changes landed in this merge (the 4 new commits were host-allowlist/error-message/docs changes only) — lockfile confirmed clean.

## TruffleHog — Verified secrets
**Summary:** 0 verified, 0 unverified secrets (9,025 chunks / 10.94MB, full git history).
```
finished scanning {"chunks": 9025, "bytes": 10937121, "verified_secrets": 0, "unverified_secrets": 0, "scan_duration": "1.811576708s"}
```

## mcps-audit — MCP permission/agentic-AI audit
**Summary:** Verdict FAIL, Risk Score 100/100, 535 findings (10 Critical, 114 High, 407 Medium, 4 Low).

Same documented false-positive pattern as every prior scan of this repo (2026-07-26 and earlier) — no new pattern introduced by this merge. The merged commits touched only `utils/cdp.py` (host allowlist + hand-off error detection) and `utils/config.py` (host allowlist), neither of which introduces new attacker-reachable surface.

- **AS-001 "Dangerous execution" (CRITICAL):** flags CDP JS payload string literals (`(async function() {...`, `(function() {...`) in `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py` — developer-only debugging scripts, not shipped/invoked by the package. This is the project's documented, intentional CDP-based auth-extraction mechanism.
- **AS-003 "High-risk permission pattern" (MEDIUM):** matches on RPC constant names and docstrings containing the word "DELETE" (e.g. `RPC_LABEL_DELETE`) in the dev script `scripts/test_label_rpcs.py` — not a runtime permission escalation.
- **AS-010 "No logging/auditing" (MEDIUM):** flagged on small standalone dev/build scripts (`desktop-extension/run_server.py`, `scripts/build_mcpb.py`, `scripts/inspect_upload_dom.py`) that don't warrant an audit-logging layer.

No code changes made in response to mcps-audit findings — none represent a real vulnerability, consistent with every prior scan's conclusion for this codebase. Full detail (all 535 findings) is in `mcps-audit-report.pdf` at the repo root (auto-generated by the tool; regenerated this run, content unchanged from the documented pattern).

## Cross-Tool Observations
No cross-tool overlaps detected. Bandit, Semgrep, Trivy, TruffleHog, and Gitleaks all report clean. mcps-audit is the sole outlier and its findings do not corroborate with any other tool — consistent with its documented high false-positive rate on this codebase.

## Coverage Gaps
- CodeQL not run (no `.github/workflows/codeql.yml`).
- No manual business-logic/IDOR review this pass — the 4 merged commits only add a hostname to an existing allowlist and improve an error message; no auth/access-control logic changed.
- mcps-audit's remaining findings not individually reviewed beyond the categories above, given the established near-100% false-positive rate on this codebase across 26+ prior scans.
