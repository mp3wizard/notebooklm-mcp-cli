# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-21 (post-merge of `origin/main`, 12 new commits: a6484bd..2f28855 — v0.9.0, `download_all` feature)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    main (merge commit 36933c7, merging origin/main)
Focus:       services/downloads.py, cli/commands/download.py, mcp/tools/downloads.py
             (new download_all / --all-notebooks / --skip-existing feature)
Include:     all supported (Python/JS/config), .venv excluded
Exclude:     .venv, .git-ignored paths
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 675 commits, ~10.44MB | — |
| Bandit | OK | 1.9.4 | 40,695 LOC (src/tests) | — |
| Semgrep (OWASP + Python) | OK | 1.170.0 | 171 files, 185 rules | 80 skipped by `.semgrepignore` |
| Trivy | OK | 0.72.0 | `uv.lock`, dependency scan | — |
| TruffleHog | OK | 3.95.9 | full git history, 8,712 chunks / 10.79MB | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock`, 88 packages | — |
| mcps-audit | OK | 1.0.0 | 187 files / 52,498 lines | — |
| CodeQL | SKIPPED | — | — | no CodeQL workflow in `.github/workflows/` |

## Manual review — `download_all` path handling

Reviewed `sanitize_filename()` and `validate_output_path()` in `services/downloads.py` for path traversal, since notebook/artifact titles (untrusted-ish, user/AI-generated content from NotebookLM) become filenames:
- `sanitize_filename()` strips `<>:"/\|?*` and control chars, collapses whitespace, truncates to 80 chars, blocks Windows reserved device names (`CON`, `PRN`, etc.) — `/` and `\` are replaced, so a title can't escape the target directory via path segments.
- `validate_output_path()` resolves the final path and enforces `NOTEBOOKLM_DOWNLOAD_DIR` sandboxing (opt-in, added in 0.8.8) plus a hardcoded block-list for sensitive dirs/dotfiles (`.ssh`, `.gnupg`, `.aws`, etc.) and sensitive filenames.
- `download_all()`/`download_all_notebooks()` both call `validate_output_path()` on the constructed notebook directory before writing.

**No path traversal or sandbox-escape issue found.** Filename collision handling (`_2`, `_3` suffixes) is also correct and can't be gamed to overwrite arbitrary files since it only appends within the already-sanitized directory.

## Bandit — Python SAST
**Summary:** 0 High, 81 Medium, 1929 Low.
All 81 Medium findings are `B108 hardcoded_tmp_directory` from `/tmp/...` mock paths in test files (`test_downloads.py`, `test_sources.py`, `test_mcp_downloads.py`, `test_cookie_parsing.py`) — test fixtures only, no production-code exposure. Same pattern as every prior scan of this repo.

## Semgrep — OWASP Top Ten / Python
**Summary:** 0 findings (185 rules, 171 files).

## Trivy — Dependency scan
**Summary:** 0 vulnerabilities (`uv.lock`, 88 packages — includes `mcp 1.28.1` fixed in the 2026-07-17 scan, confirmed still current).

## TruffleHog — Verified secrets
**Summary:** 0 verified, 0 unverified secrets (8,712 chunks / 10.79MB, full git history).

## Gitleaks — Secrets (filesystem + history)
**Summary:** 0 leaks (675 commits scanned).

## OSV-Scanner — SCA via OSV.dev
**Summary:** 0 issues, 88 packages — cross-confirms Trivy.

## mcps-audit — MCP permission/agentic-AI audit
**Summary:** Verdict FAIL, Risk Score 100/100, 526 findings (10 Critical, 113 High, 400 Medium, 3 Low).

Same documented false-positive pattern as every prior scan (2026-07-17 and earlier) — no new pattern introduced by this merge:
- `AS-001 "Dangerous execution"` on `scripts/inject_cookies_and_inspect.py`, `scripts/inspect_upload_dom.py` — JS executed inside the user's own local Chrome session via CDP to extract auth cookies for `nlm login`; documented, intentional (CLAUDE.md Authentication section).
- `AS-003 "High-risk permission pattern"` on `scripts/test_label_rpcs.py` — flags the string `RPC_LABEL_DELETE` in a test script docstring/comment, not an unguarded production deletion path.
- `AS-010 "No logging/auditing"` — informational, hits one-off dev/debug scripts (`desktop-extension/run_server.py`, `scripts/build_mcpb.py`, etc.), not the MCP server runtime.

No fix applied — these are the same accepted false positives as the 2026-07-17 report; nothing in the `download_all` merge touches these files.

## Cross-Tool Observations
- Trivy and OSV-Scanner independently confirm 0 dependency vulnerabilities.
- Gitleaks, TruffleHog, and Semgrep all independently report zero secrets.
- mcps-audit's Critical/High findings are entirely on pre-existing dev/debug scripts untouched by this merge — no new agentic-AI risk introduced by `download_all`.

## Findings requiring action this run
**None.** No Very High / High / Medium findings to fix — clean scan, and mcps-audit noise is pre-existing accepted false positives unrelated to the merged changes.

## Coverage Gaps
- Not covered: business logic correctness, IDOR/authorization beyond static pattern matching, runtime behavior.
- CodeQL skipped — no CodeQL GitHub Actions workflow configured.
- mcp-scan / skillspector LLM mode / config-audit / skill-audit / mcp-exfil-scan not re-run this cycle (last full run: 2026-07-17, all clean/false-positive; no repo config or skill files changed since).
