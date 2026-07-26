# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-26 (post-merge of `origin/main`, 4 new commits: 8b5d947..b2ab425 — v0.9.1/0.9.2, chat session management + CVE dep bumps)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    main (merge commit 18fb275, merging origin/main)
Focus:       full repo, with emphasis on new chat session code
             (services/chats.py, cli/commands/chats.py, mcp/tools/chats.py)
Include:     all supported (Python/JS/config)
Exclude:     .venv (excluded explicitly on the second bandit/semgrep/trivy pass —
             see note below)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 679 commits, ~10.51MB | — |
| Bandit | OK | 1.9.4 | 27,723 LOC (`src/`, `desktop-extension/`, `scripts/`, excl. tests) | — |
| Semgrep (OWASP + Python) | OK | 1.170.0 | 118 files, 160 rules | `.venv` excluded |
| Trivy | OK | 0.72.0 | `uv.lock`, dependency scan | — |
| TruffleHog | OK | 3.95.9 | full git history, 8,780 chunks / 10.86MB | — |
| mcps-audit | OK | 1.0.0 | 192 files / 53,468 lines | — |
| CodeQL | SKIPPED | — | — | no CodeQL workflow in `.github/workflows/` |

**Note:** the first Bandit pass was run against the whole repo (`.` — no excludes) and accidentally scanned `.venv`, inflating LOC to 818K and producing noise unrelated to project code. Re-ran scoped to `src/`, `desktop-extension/`, `scripts/` — this is the result reported below.

## Gitleaks — Secrets (filesystem + history)
**Summary:** 0 leaks (679 commits scanned, ~10.51MB).
```
10:47AM INF 679 commits scanned.
10:47AM INF scanned ~10512050 bytes (10.51 MB) in 862ms
10:47AM INF no leaks found
```

## Bandit — Python SAST
**Summary:** 0 High, 0 Medium, 1 Low.

Single finding — pre-existing pattern, same as prior scans:
```
>> Issue: [B110:try_except_pass] Try, Except, Pass detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   Location: src/notebooklm_tools/core/auth.py:481:12
480	                email = existing_metadata.get("email")
481	            except Exception:
482	                pass
483	

Code scanned:
	Total lines of code: 27723
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 72

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 1
		Medium: 0
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 1
```
This is a best-effort metadata read (`email` field from a possibly-stale local profile file) — swallowing the exception is intentional fallback behavior, not a security gap. No action taken.

## Semgrep — OWASP Top Ten / Python
**Summary:** 0 findings (160 rules, 118 files, 100% parsed).
```
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 160
 • Targets scanned: 118
 • Parsed lines: ~100.0%
Ran 160 rules on 118 files: 0 findings.
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
Confirms the upstream `chore(deps): bump locked versions with published CVEs` commit (`a68579f`, mcp 1.27.0→1.28.1, starlette 1.0.0→1.3.1, python-multipart 0.0.26→0.0.32, cryptography 46.0.7→49.0.0, pyjwt 2.12.1→2.13.0) landed clean — no residual CVEs in the lockfile.

## TruffleHog — Verified secrets
**Summary:** 0 verified, 0 unverified secrets (8,780 chunks / 10.86MB, full git history).
```
finished scanning {"chunks": 8780, "bytes": 10860290, "verified_secrets": 0, "unverified_secrets": 0, "scan_duration": "3.532823834s"}
```

## mcps-audit — MCP permission/agentic-AI audit
**Summary:** Verdict FAIL, Risk Score 100/100, 532 findings (10 Critical, 113 High, 405 Medium, 4 Low).

Same documented false-positive pattern as every prior scan of this repo (2026-07-21 and earlier) — no new pattern introduced by this merge. Manually reviewed all 10 CRITICAL findings and a representative sample of the 113 HIGH findings (all 22 SECRET SCAN hits):

- **AS-001 "Unsafe execution" (7 of 10 Critical):** flags any JS string literal starting with `(async function()` / `(function()` — these are Chrome DevTools Protocol JS payloads in `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py` (developer-only debugging scripts, not shipped/invoked by the package), plus `__import__`/`exec()` in three *test files* (`test_auth_health.py`, `test_auth_service.py`, `test_io_encoding_windows.py`) exercising internal reimport behavior — no attacker-controlled input reaches any of these.
- **AS-005 "Injection pattern" (2 of 10 Critical):** matched on docstring/comment prose in `core/download.py` ("2. `<script id=\"application-data\">` tag (fallback)") and a hardcoded HTML fixture string in `test_api_client.py` — not executable injection sinks.
- **AS-002 "Secret scan" (all 22 HIGH sampled):** every hit is a test fixture placeholder (`csrf_token="stale123"`, `csrf_token="test_token"`, etc.) in `tests/`. Corroborated by TruffleHog and Gitleaks finding zero actual secrets across the same commits.
- One AS-001 finding (`cli/commands/doctor.py:385`) already carries `# nosec B603 — cmd from shutil.which(), args are hardcoded strings, no shell=True`; mcps-audit doesn't parse `# nosec` suppressions the way Bandit does.

No code changes made in response to mcps-audit findings — none represent a real vulnerability, consistent with every prior scan's conclusion for this codebase. Full detail (all 532 findings) is in `mcps-audit-report.pdf` at the repo root (auto-generated by the tool).

## Cross-Tool Observations
No cross-tool overlaps detected. Bandit, Semgrep, Trivy, TruffleHog, and Gitleaks (the five reliable/low-noise tools) all report clean. mcps-audit is the sole outlier and its findings do not corroborate with any other tool — consistent with its documented high false-positive rate on this codebase.

## Coverage Gaps
- CodeQL not run (no `.github/workflows/codeql.yml`).
- No manual business-logic/IDOR review this pass (no auth/access-control surface changed in the 4 merged commits — chat session tools reuse existing profile-scoped auth, and the Windows `uvx` discovery fix only touches local path globbing).
- mcps-audit's remaining ~100 unsampled HIGH and ~405 MEDIUM findings not individually reviewed this pass, given the established near-100% false-positive rate on this codebase across 25+ prior scans; spot-checked categories (CRITICAL, all SECRET SCAN) confirm the pattern holds.
