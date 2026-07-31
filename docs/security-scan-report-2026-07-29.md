# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-29T10:15:00+07:00
**Context:** Post-merge scan after merging `origin/main` (v0.9.5 — WSL2 mirrored networking fix)
**Tools run:** Gitleaks, Bandit, Semgrep, Trivy, TruffleHog, mcps-audit
**Tools skipped:** CodeQL (no `codeql.yml` workflow configured in `.github/workflows/`)

## Pre-flight Summary
| Tool | Status | Version |
|------|--------|---------|
| Gitleaks   | OK | 8.30.1 |
| Bandit     | OK | 1.9.4 |
| Semgrep    | OK | 1.170.0 |
| Trivy      | OK | 0.72.0 |
| TruffleHog | OK | 3.95.9 |
| CodeQL     | SKIPPED | not configured for this repo |
| mcps-audit | OK | 1.0.0 |

## Gitleaks — Secrets in git history + filesystem
**Summary:** 0 leaks. 689 commits scanned, ~10.6 MB.
```
no leaks found
```

## Bandit — Python SAST
Scanned `src/`, `tests/`, `scripts/` (excluded `.venv` — vendored deps were skewing counts to 7000+ issues on first pass).
**Summary:** 2006 Low, 81 Medium, 0 High.
- All 81 Medium findings are `B108:hardcoded_tmp_directory` — string literals like `/tmp/audio.m4a`, `/tmp/exports/...` used as mock/fixture values in `tests/`. No occurrences in `src/`. False positives, no code change needed.
- Low findings are almost entirely `B101:assert_used` (expected — `assert` is idiomatic in pytest) and `B404` subprocess-import notices in `tests/test_wsl.py`, already covered by justified `# nosec` markers in the corresponding `src/` code.
- 70 issues suppressed via existing `# nosec` markers (all in `src/notebooklm_tools/utils/wsl.py`, `cli/main.py`) — reviewed below.

## Semgrep — Multi-language SAST (p/python + p/owasp-top-ten)
**Summary:** 0 findings. 157 rules run across 116 tracked files.
```
Ran 157 rules on 116 files: 0 findings.
```

## Trivy — Dependency vulnerabilities
**Summary:** 0 vulnerabilities in `uv.lock`.
```
┌─────────┬──────┬─────────────────┬─────────┐
│ Target  │ Type │ Vulnerabilities │ Secrets │
├─────────┼──────┼─────────────────┼─────────┤
│ uv.lock │  uv  │        0        │    -    │
└─────────┴──────┴─────────────────┴─────────┘
```

## TruffleHog — Secrets (git history, live-verified)
**Summary:** 0 verified, 0 unverified secrets. 9056 chunks / 10.96 MB scanned.
```
"chunks": 9056, "bytes": 10959703, "verified_secrets": 0, "unverified_secrets": 0
```

## mcps-audit — MCP/Agentic AI heuristic scan
**Summary:** Verdict FAIL (heuristic scorer, generic MCPS-SDK checklist not applicable to this project) — 10 Critical, 114 High, 408 Medium, 4 Low across 195 files. Full report: `mcps-audit-report.pdf` (generated in repo root, not committed).

All 10 Critical findings manually reviewed — none are real vulnerabilities:
| File | Finding | Assessment |
|------|---------|------------|
| `scripts/inject_cookies_and_inspect.py:107,158` | "Dangerous execution: async function()" | Dev-only CDP debugging script, executes JS in the user's own local Chrome session under their control. Not shipped, not reachable by untrusted input. |
| `scripts/inspect_upload_dom.py:104` | same pattern | Same — local dev tooling. |
| `src/notebooklm_tools/cli/commands/doctor.py:385` | "Dangerous execution: subprocess.run" | Already `# nosec B603` — cmd resolved via `shutil.which()`, args hardcoded. |
| `src/notebooklm_tools/core/download.py:1103,1131` | "Known injection pattern" | False positive — heuristic matches the *string* `<script id="application-data">` inside a regex/docstring used to parse the app's own HTML response with `json.loads`; no `eval`/`exec` involved. |
| `tests/services/test_auth_health.py:331`, `tests/services/test_auth_service.py:153`, `tests/test_io_encoding_windows.py:37` | "Dangerous execution: `__import__`/`exec`" | Test-only dynamic imports for testing import-time behavior, not attacker-reachable. |
| `tests/test_api_client.py:119` | "Known injection pattern" | Test fixture string, not executed as code. |

The 114 High / 408 Medium findings are dominated by the same heuristic classes (subprocess-import notices, "no audit logging" on CLI scripts, RPC constant names containing the substring `DELETE`) — a scanner tuned for generic agentic/MCP servers with SDK-level passport/audit-log expectations this CLI tool doesn't use. Not spot-checked individually beyond the Critical tier given the pattern above; none touch the files changed by this merge (`utils/wsl.py`, `cli/main.py`).

### New code in this merge (`wsl.py`, `cli/main.py`) — manual review
All new/changed `subprocess.run`/`Popen` calls use fixed argument lists (never `shell=True`), carry existing `# nosec B603 B607` justifications, and this merge *added* `timeout=` to every PowerShell subprocess call (firewall check/create/remove) that previously had none — a hardening improvement, not a regression.

## Cross-Tool Observations
No cross-tool overlaps — Gitleaks/TruffleHog/Semgrep/Trivy all report clean; only Bandit (test-fixture false positives) and mcps-audit (heuristic false positives on dev scripts/tests) produced findings, and neither tool corroborates the other's specific findings.

## Coverage Gaps
- **CodeQL**: not configured for this repo (no `codeql.yml` workflow) — no semantic dataflow analysis performed.
- **Business logic / IDOR**: not covered by any tool that ran — this CLI operates against Google's NotebookLM API using user-supplied cookies; access control is delegated to Google's backend, out of scope for static analysis.
- **Runtime behavior**: none of the tools exercise the actual WSL2 networking-mode detection or PowerShell subprocess paths added in this merge; only reviewed statically. The merge commit claims "1246 tests pass" — recommend running `uv run pytest` to confirm before relying on the new `tests/test_wsl.py` coverage.
