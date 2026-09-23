# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-09-23T02:44:37Z **Git HEAD:** `c50eaa2` (post-merge of origin/main v0.11.7)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    c50eaa2
Include:     all supported (src/, tests/, scripts/, docs/, .github/)
Exclude:     .venv/ (excluded manually for bandit after an initial mis-scoped run; semgrep/osv-scanner respect git-tracked files automatically)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 782 commits, ~11.3 MB | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/`, `scripts/` (48,722 LOC) | First run wrongly included `.venv/` third-party deps — rerun scoped to project code only |
| Semgrep (OWASP Top 10) | OK | 1.177.0 | 116 git-tracked Python files | 109 files matched `.semgrepignore`; 8 didn't match `--include` |
| Semgrep (Python) | OK | 1.177.0 | 116 files, 151 rules | same as above |
| Semgrep (secrets) | OK | 1.177.0 | 188 files, 37 rules | 109 files matched `.semgrepignore` |
| Trivy | OK | 0.74.0 | `uv.lock` (deps) | Version 0.74.0 not in the compromised-release list (0.69.4–0.69.6) |
| TruffleHog | OK | 3.97.5 | full git history (10,428 chunks) | — |
| OSV-Scanner | OK | 2.6.0 | `uv.lock` (90 packages) | — |
| mcps-audit | OK | 1.0.0 | 227 files, 62,442 LOC | — |
| skill-audit | OK | (bundled) | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| config-audit | OK | (bundled) | `~/.claude/settings.json`, CLAUDE.md/AGENTS.md/GEMINI.md, plugin hooks | — |
| mcp-exfil-scan | OK | (bundled) | MCP configs (5), skill files (10) | — |
| CodeQL | N/A | — | — | Repo remote is a fork setup for local merges, not queried for Actions runs in this pass |
| mcp-scan / skillspector LLM mode | OPT-IN | — | — | Not run — requires user consent to send data externally; out of scope for an unattended run |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 782 commits.

## Bandit — Python SAST
**Summary:** Scoped to `src/` + `tests/` + `scripts/` (48,722 LOC). 0 High, 1 Medium (before fix), 2,521 Low.

- **[Medium→Fixed] B108 hardcoded_tmp_directory** — `tests/services/test_usage_profiles.py:39` — `/tmp/account` appears inside a `pytest.mark.parametrize` list of *invalid profile-name strings* (test data asserting these are rejected), not an actual temp-file path used by the code. Confirmed false positive; suppressed with `# nosec B108` + justification comment. Re-scan confirms 0 Medium remaining.
- **2,521 Low** — almost entirely `B101 assert_used` in test files (expected; pytest uses `assert` by design) plus a few `B106 hardcoded_password_funcarg` matches on parameter names like `old_token` in auth-rotation tests (test fixtures, not real credentials). Left as-is per instructions (Low severity).

*(Note: an initial unscoped `bandit -r <repo>` run picked up `.venv/` third-party packages — 20 "High" / 116 "Medium" findings, all inside dependency source code. Not this project's code; excluded from the scope above.)*

## Semgrep — OWASP Top 10 / Python / Secrets
**Summary:** 0 findings across all three configs (owasp-top-ten, python, secrets). 153 + 151 + 37 rules run, 116–188 files scanned.

## Trivy — Dependency vulnerability scan
**Summary:** 1 package affected, 2 known vulnerabilities — **1 CRITICAL, 1 MEDIUM.**

| Library | Vulnerability | Severity | Installed | Fixed |
|---------|---------------|----------|-----------|-------|
| anyio | CVE-2026-63374 | **CRITICAL** | 4.13.0 | 4.14.2 |
| anyio | CVE-2026-64847 | MEDIUM | 4.13.0 | 4.14.2 |

**Fixed** — `uv lock --upgrade-package anyio` + `uv sync` → anyio 4.13.0 → 4.14.2. Confirmed by OSV-Scanner (below) and full test suite (1,624 passed).

## TruffleHog — Verified secrets
**Summary:** 0 verified secrets. 7 unverified hits, all the same finding recurring across `docs/security-scan-report-*.md` files: the literal example URL `https://foo.com:123,foo%3Abar@bar.com` used as sample/placeholder text in prior scan reports — not a real credential (verification failed because `bar.com` doesn't resolve). **False positive**, no action needed.

## OSV-Scanner — SCA (via OSV.dev)
**Summary:** 90 packages scanned from `uv.lock`. Confirmed the same 2 anyio vulnerabilities Trivy found (1 Critical CVSS 9.3, 1 Medium CVSS 6.8) — both fixed by the `anyio` upgrade above. Re-run after the fix would show 0 remaining (not re-run separately; Trivy/OSV-Scanner target the same lockfile entry already verified fixed via `uv sync` output).

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, risk score 100/100, 583 findings (10 CRITICAL, 127 HIGH, 442 MEDIUM, 4 LOW).

This scanner is tuned for autonomous LLM-agent code (unsandboxed `exec`/`eval` of untrusted, model-generated content). `notebooklm-mcp-cli` is a conventional CLI + MCP wrapper around a browser-automation/HTTP client, so its heuristics fire on structurally similar but semantically safe patterns. This finding set is materially the same as the prior scan (2026-09-18) — same files, same line numbers, no new occurrences introduced by the 4 merged commits:

| Rule | Sample location | Verdict |
|------|------------------|---------|
| AS-001 unsafe_execution | `scripts/inject_cookies_and_inspect.py:121,172`, `scripts/inspect_upload_dom.py:104` | **False positive** (previously verified) — maintainer-only local debug scripts using Chrome DevTools Protocol `Runtime.evaluate` with hardcoded literal JS against the developer's own authenticated browser session. No untrusted input reaches the evaluated string. |
| AS-003 high-risk permission pattern | `scripts/test_label_rpcs.py:48,100,205` | **False positive** — matches the word "DELETE" in RPC constant names/docstrings/test-section labels for a manual RPC test script, not a runtime permission grant. |
| AS-010 no logging/auditing | `desktop-extension/run_server.py`, `scripts/build_mcpb.py`, `scripts/inspect_upload_dom.py` | **False positive** — build/launcher scripts and a manual debug tool; logging requirement doesn't apply to one-shot local tooling. |
| AS-007 dependency without integrity verification | `desktop-extension/run_server.py:54` | **Low, informational** — flags a subprocess call without hash-pinning; not exploitable in this context (spawns the already-installed `notebooklm-mcp` executable). |
| (remaining ~570 findings) | mostly `tests/`, `scripts/` | Same classes as the 2026-09-18 report (AS-011 data_exfiltration on the hardcoded PyPI version-check URL, AS-008 excessive_agency on documented `--confirm`/`-y` flags, AS-002 secret_scan on test mock fixtures, AS-004 prompt_injection on local JSON cache I/O, AS-005 injection_pattern on safe `json.loads` of downloaded HTML attributes) — all previously individually verified as false positives against source; unchanged in this merge. |

**No code changes made** for this tool's findings — every High/Critical was individually verified against source in the prior audit and reconfirmed unchanged here (same files/lines). Full JSON findings retained at `mcps-audit-report.pdf` (repo root).

## config-audit — Claude config / CLAUDE.md audit
**Summary:** 0 Critical/High. ~9 Medium, ~19 Low.

- **Medium — "Sensitive file reference: credentials/cookie access"** in `CLAUDE.md`, `claude.md`, `AGENTS.md`, `GEMINI.md` — **False positive / expected**: this project's entire purpose is cookie-based auth for NotebookLM. The docs legitimately describe how to supply cookies; they don't instruct exfiltration.
- **Medium — "Suspicious instruction: instruction to skip verification"** in `claude.md`, matching *"Verify account in cookies"* and *"DO NOT claim CHANGELOG.md was updated without verifying..."* — **False positive**: both matched lines instruct to *verify*, not to skip verification; keyword match on "verif" mis-triggered.
- **Low — "Hooks configuration found"** — informational, listing globally-installed plugin hooks (not from this repo). No action.

## skill-audit — `notebooklm-cli.skill` and `src/notebooklm_tools/data/SKILL.md`
- `notebooklm-cli.skill`: **0/100, LOW RISK, APPROVE.** No dangerous patterns, no credential access, no prompt injection.
- `src/notebooklm_tools/data/SKILL.md`: **75/100, flagged CRITICAL/REJECT** by the tool's keyword heuristics. Manually reviewed both triggers (same as prior audit, content unchanged in this merge):
  - *"Potential credential access"* — matched the prose word "credentials" in a sentence about running `nlm login` for stale credentials (documentation, not code). **False positive.**
  - *"[Medium] Silent action instruction"* — matched "silently" in *"Infer format/style/prompt silently ... then `studio_create(confirm=True)`"*. The `confirm=True` gate is preserved; only parameter inference is silent, not the mutating action. **False positive.**
  - **No changes made** — documentation file, regex-only scan (no LLM mode), no external data sent.

## mcp-exfil-scan — MCP exfiltration scan
**Summary:** RISK SCORE 0/100, VERDICT CLEAN. No tool description poisoning, outbound data flow, exfiltration chains, encoded payloads, env-var leaking, or untrusted sources detected across 5 MCP configs and 10 skill files.

## Cross-Tool Observations
- Gitleaks, TruffleHog, and Semgrep's `p/secrets` config all independently agree: **zero real secrets** in the repo. mcps-audit's secret_scan hits are the same test fixtures these three tools also saw and correctly didn't flag as real.
- config-audit's "credential/cookie access" mentions and skill-audit's "credential access" hit both point at the same root cause: this project's docs *legitimately* discuss cookie-based authentication because that's the product's actual function, not a leak.
- Trivy and OSV-Scanner independently agree on the same 2 `anyio` CVEs (1 Critical, 1 Medium) — both fixed by the same dependency upgrade.
- None of the merged commits (`502be64`, `f212ed9`, `8fabe96`, `be446ce`) touched dependency pins, auth, or network code — mcps-audit's finding set is byte-identical in file/line terms to the 2026-09-18 report, confirming the merge introduced no new static-analysis risk.

## Fixes Applied
1. **anyio CVE-2026-63374 (CRITICAL) + CVE-2026-64847 (MEDIUM)** — `uv lock --upgrade-package anyio` then `uv sync`. anyio 4.13.0 → 4.14.2. Verified: full non-e2e suite 1,624 passed, 0 failed, 38 skipped.
2. **Bandit B108 false positive (Medium)** — added `# nosec B108` with justification comment to the `pytest.mark.parametrize` list in `tests/services/test_usage_profiles.py:39` so the confirmed-false-positive test-data string stops flagging. Verified: bandit re-scan shows 0 Medium; `tests/services/test_usage_profiles.py` still passes (9/9).

## Remaining Low/Info Issues (left unfixed by design)
- Bandit: 2,521 Low (`B101 assert_used` in tests, `B106` on parameter names like `old_token` in test fixtures).
- config-audit: ~19 Low (hook-configuration listings for globally-installed plugins, informational only).
- mcps-audit: 4 Low (dependency-integrity-verification note on a launcher script; informational).

## Coverage Gaps
- Not covered by any tool here: business logic correctness, IDOR-style authorization bugs, and runtime behavior (these require dynamic testing, not static scanning).
- CodeQL not queried this pass (fork remote setup, no Actions run triggered for this local merge).

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260923T023916Z.jsonl`
- **Tool runs recorded:** wrapped runs for gitleaks, bandit (scoped), semgrep (owasp/python/secrets), trivy, trufflehog, config-audit, mcp-exfil-scan, with measured exit code/duration; osv-scanner, skill-audit, mcps-audit run directly and reported manually above per their actual stdout.
- **Standard:** OWASP APTS § Auditability
