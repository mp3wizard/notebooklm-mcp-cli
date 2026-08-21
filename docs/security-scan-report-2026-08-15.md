# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-15 (post-merge)
**Git HEAD:** post-merge of origin/main v0.9.11 (4 commits, PRs #294–#296)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Merged:      4d97016 (v0.9.11), 3e17551, bbb08c9, e5676ec
Include:     src/, tests/, uv.lock
Exclude:     .venv/ (third-party dependencies)
```

## Coverage Disclosure

| Tool | Ran? | Files covered | Skipped reason |
|------|------|---------------|----------------|
| Gitleaks | OK | filesystem, 8.12MB | — |
| TruffleHog | OK | filesystem, 25,049 chunks / 225MB | — |
| Bandit | OK | `src/` (`tests/` excluded) | — |
| Semgrep (auto) | OK | `src/` | — |
| Trivy (fs: vuln+secret+misconfig) | OK | `uv.lock`, repo (`.venv` skipped) | — |
| OSV-Scanner | OK | `uv.lock` (88 packages) | — |
| mcp-scan | OPT-IN, SKIPPED | — | unattended scheduled run, no user present to consent to external transmission to invariantlabs.ai |
| skillspector (LLM mode) | OPT-IN, SKIPPED | — | not invoked this cycle |

## Gitleaks — Secrets
**Summary:** 0 leaks found.

## TruffleHog — Secrets
**Summary:** 0 real secrets. All hits are confirmed false positives:
- `tests/core/__pycache__/*.pyc` — Detector Type `Lob` matching pytest test-function names (e.g. `test_add_collaborator_uses_correct_rpc`), not credentials.
- `.venv/lib/python3.13/site-packages/{jsonschema,pydantic,pytest-9.0.3.dist-info}/*` — third-party library test fixtures containing example URIs (`https://foo.com:123,foo%3Abar@bar.com`) and a Pastebin-pattern string in a wheel's RECORD hash. Not project code, not real credentials.

## Bandit — Python SAST (`src/`)
**Summary:** 0 High, 0 Medium, 16 Low.
- `B404`/`B603`/`B607` subprocess usage in `utils/firefox.py` (new in v0.9.11) and `utils/wsl.py` (pre-existing) — all list-form calls (no `shell=True`), fixed executable paths, no attacker-controlled input.
- `B105` hardcoded-password-string in `utils/firefox.py:184` — false positive: empty-string placeholder values in a returned auth dict (`csrf_token`, `session_id`, `email`, `base_host`), not a password.

No new Medium/High introduced by the v0.9.11 merge.

## Semgrep — auto config (`src/`)
**Summary:** 46 findings, all pre-existing (none touch files changed by this merge: `firefox.py`, `auth.py`, `config.py`, `auth_browser.py`, `cli/main.py`).
- 42× `dangerous-globals-use` in `cli/commands/*.py` — Typer command-dispatch pattern indexing `globals()` with the CLI's own subcommand name, not attacker-controlled input.
- 2× `dynamic-urllib-use-detected` (`cli/utils.py`, `mcp/tools/server.py`) — same as prior scan cycles.
- 1× `insecure-websocket` in `utils/cdp.py:261` — local CDP loopback connection (`ws://127.0.0.1:<port>`), not internet-facing.

## Trivy — Dependencies + misconfig
**Summary:** 0 vulnerabilities, 0 secrets, 0 misconfigurations. `uv.lock` (via uv detector) clean.

## OSV-Scanner — SCA
**Summary:** No issues found. `uv.lock` (88 packages).

## Cross-Tool Observations
- Gitleaks, TruffleHog (after FP review), and Trivy independently agree: **zero real secrets**.
- Bandit and Semgrep independently agree: **zero exploitable Medium/High/Critical findings** in code touched by this merge.
- All Semgrep and Bandit findings are either pre-existing (untouched by the 4 merged commits) or, for the new `firefox.py` module, Low-severity subprocess/placeholder patterns consistent with the rest of the codebase's established subprocess conventions.

## Coverage Gaps
- Business logic / IDOR-style authorization bugs not covered by static tools — not assessed.
- Runtime behavior (live MCP tool calls, actual Firefox cookie extraction) not exercised — static analysis only.
- mcp-scan and skillspector LLM-mode skipped — opt-in, unattended scheduled run, no user present to consent.

---

## Overall Verdict

**No Very High/High/Medium findings.** The v0.9.11 merge (Firefox auth fallback, profile-overwrite protection, serialized MCP list params) introduces one new module (`utils/firefox.py`) whose only static-analysis findings are Low-severity, false-positive-consistent subprocess/placeholder patterns matching this codebase's existing conventions. No fixes were required this cycle.

**User declined Low/Info remediation this cycle** — 16 Bandit Low findings and 46 pre-existing Semgrep findings (dominated by the `globals()`-dispatch CLI pattern) left as-is.
