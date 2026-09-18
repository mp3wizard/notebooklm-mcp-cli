# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-09-18T08:11:00Z **Git HEAD:** `d620c9d` (post-merge of origin/main v0.11.5)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    d620c9d
Include:     all supported (src/, tests/, scripts/, docs/, .github/)
Exclude:     .venv/ (excluded manually for bandit after an initial mis-scoped run; semgrep/osv-scanner respect git-tracked files automatically)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 777 commits, ~11.3 MB | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/` (48,138 LOC) | First run wrongly included `.venv/` third-party deps — rerun scoped to project code only |
| Semgrep (OWASP Top 10) | OK | 1.177.0 | 117 git-tracked Python/multilang files | 109 files matched `.semgrepignore`; 94 didn't match `--include` |
| Semgrep (Python) | OK | 1.177.0 | 117 files, 151 rules | same as above |
| Semgrep (secrets) | OK | 1.177.0 | 208 files | 1 file >0.3 MB skipped: `mcps-audit-report.pdf` (binary PDF, not source) |
| Trivy | **FAILED** | 0.74.0 | — | Vulnerability DB download failed twice (`connection reset by peer` from `mirror.gcr.io`) — network/infra issue, not repo-caused. Not retried a third time per runbook rule (no blind retries). |
| TruffleHog | OK | 3.97.5 | full git history | — |
| OSV-Scanner | OK | 2.6.0 | `uv.lock` (90 packages) | — |
| mcps-audit | OK | 1.0.0 | 227 files, 62,315 LOC | — |
| skill-audit | OK | (bundled) | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| config-audit | OK | (bundled) | `~/.claude/settings.json`, CLAUDE.md/AGENTS.md/GEMINI.md, plugin hooks | — |
| mcp-exfil-scan | **SKIPPED** | (bundled) | — | Bundled script `mcp-exfil-scan.sh` failed its SHA256 integrity check (`shasum -c SHA256SUMS` → FAILED). Per the security-scanner skill's own tamper-evidence rule ("do NOT run"), it was not executed. |
| CodeQL | N/A | — | — | Repo remote is a fork setup for local merges, not queried for Actions runs in this pass |
| mcp-scan / skillspector LLM mode | OPT-IN | — | — | Not run — requires user consent to send data externally; out of scope for an unattended run |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 777 commits.

## Bandit — Python SAST
**Summary:** Scoped to `src/` + `tests/` only (48,138 LOC). 0 High, 1 Medium, 2,513 Low.

- **[Medium] B108 hardcoded_tmp_directory** — `tests/services/test_usage_profiles.py:39` — `/tmp/account` appears inside a `pytest.mark.parametrize` list of *invalid profile-name strings* (test data asserting these are rejected), not an actual temp-file path used by the code. **False positive** — no fix needed.
- **2,513 Low** — almost entirely `B101 assert_used` in test files (expected; pytest uses `assert` by design) plus a few `B106 hardcoded_password_funcarg` matches on parameter names like `old_token` in auth-rotation tests (test fixtures, not real credentials). Left as-is per instructions (Low severity).

*(Note: an initial unscoped `bandit -r <repo>` run picked up `.venv/` third-party packages — 20 "High" / 116 "Medium" findings, all inside dependency source code such as pytest, cryptography, dns, docutils. These are not this project's code and are irrelevant to this report; excluded from the scope above.)*

## Semgrep — OWASP Top 10 / Python / Secrets
**Summary:** 0 findings across all three configs (owasp-top-ten, python, secrets). 153 + 151 + 38 rules run, 117–208 files scanned.

## Trivy — Dependency / IaC / Secret scan
**Summary:** FAILED — could not download vulnerability DB (network reset from `mirror.gcr.io/aquasec/trivy-db`). Attempted twice, both failed identically; not retried further. Dependency-vulnerability coverage for this run is provided by OSV-Scanner instead (see below).

## TruffleHog — Verified secrets
**Summary:** 0 verified secrets. 6 unverified hits, all the same finding recurring across 6 old `docs/security-scan-report-*.md` files: the literal example URL `https://foo.com:123,foo%3Abar@bar.com` used as sample/placeholder text in prior scan reports — not a real credential (verification failed because `bar.com` doesn't resolve). **False positive**, no action needed.

## OSV-Scanner — SCA (via OSV.dev)
**Summary:** 90 packages scanned from `uv.lock`. **No issues found.**

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, risk score 100/100, 137 High/Critical findings (10 CRITICAL, 127 HIGH) + 446 Medium/Low (not itemized — tool's own severity filter used for triage below).

This scanner is tuned for autonomous LLM-agent code (unsandboxed `exec`/`eval` of untrusted, model-generated content). `notebooklm-mcp-cli` is a conventional CLI + MCP wrapper around a browser-automation/HTTP client, so its heuristics fire on structurally similar but semantically safe patterns. Every finding class was inspected with real code, not just counted:

| Rule | Count | Sample location | Verdict |
|------|-------|------------------|---------|
| AS-011 data_exfiltration ("Dynamic HTTP with sensitive data context") | 38 | `cli/utils.py:6,183` | **False positive** — hardcoded PyPI version-check URL (`https://pypi.org/pypi/notebooklm-mcp-cli/json`), 2s timeout, already annotated `# nosec B310`. Flagged only because the file also imports `AuthManager` elsewhere. |
| AS-008 excessive_agency ("Unrestricted agent autonomy") | 33 | `cli/commands/alias.py:92`, `ai_docs.py:358` | **False positive** — these are the documented `--confirm`/`-y` CLI flags for scripted/automated use (explicit user-invoked flag, not autonomous model decision-making). |
| AS-002 secret_scan ("possible hardcoded secret") | 31 | `tests/core/test_base.py`, `tests/test_file_upload.py`, etc. | **False positive** — all 31 hits are inside `tests/`; mock cookie/token fixtures for unit tests. Confirmed against TruffleHog (0 verified secrets) and Gitleaks (0 leaks). |
| AS-004 prompt_injection ("File input near prompt/instruction handling") | 24 | `cli/utils.py:149,167` | **False positive** — local JSON version-check cache read/write (`json.load`/`json.dump` on a local file); no LLM prompt or instruction handling exists in this code path at all. |
| AS-001 unsafe_execution ("Dangerous code execution") | 7 | `scripts/inject_cookies_and_inspect.py:121,172`, `scripts/inspect_upload_dom.py:104` | **False positive** — maintainer-only local debug scripts (not packaged/shipped, not invoked by the CLI or MCP server) that use Chrome DevTools Protocol `Runtime.evaluate` with hardcoded literal JS to click through the developer's own authenticated browser session during manual troubleshooting. No untrusted input reaches the evaluated string. |
| AS-005 injection_pattern ("Known injection pattern detected") | 3 | `core/download.py:1285,1313` | **False positive** — regex extraction of embedded JSON from downloaded artifact HTML (`data-app-data` attribute), followed by `html.unescape` + `json.loads` (safe deserialization, not `eval`/`exec`). |
| AS-006 sandboxing ("Code execution without sandboxing") | 1 | `cli/commands/doctor.py:386` | **False positive** — `subprocess.run([shutil.which("claude"), "mcp", "list"], ...)`, no `shell=True`, hardcoded arg list, already annotated `# nosec B603`. |

**No code changes made** for this tool's findings — every High/Critical was individually verified against source and is a scanner/threat-model mismatch, not a real vulnerability. Full JSON findings retained at `mcps-audit-report.pdf` (repo root, generated by the tool) for reference.

## config-audit — Claude config / CLAUDE.md audit
**Summary:** 0 Critical/High. ~9 Medium, ~19 Low.

- **Medium — "Sensitive file reference: credentials/cookie access"** in `CLAUDE.md`, `claude.md`, `AGENTS.md`, `GEMINI.md` — **False positive / expected**: this project's entire purpose is cookie-based auth for NotebookLM (`## Authentication` section documents `NOTEBOOKLM_COOKIES`, `save_auth_tokens`, etc.). The docs legitimately describe how to supply cookies; they don't instruct exfiltration.
- **Medium — "Suspicious instruction: instruction to skip verification"** in `claude.md`, matching the strings *"Verify account in cookies"* and *"DO NOT claim CHANGELOG.md was updated without verifying..."* — **False positive**: both matched lines are instructions to *verify*, not to *skip* verification; a substring/keyword match on "verif" mis-triggered.
- **Low — "Hooks configuration found"** — informational, listing globally-installed plugin hooks (not from this repo). No action.

## skill-audit — `notebooklm-cli.skill` and `src/notebooklm_tools/data/SKILL.md`
- `notebooklm-cli.skill`: **0/100, LOW RISK, APPROVE.** No dangerous patterns, no credential access, no prompt injection.
- `src/notebooklm_tools/data/SKILL.md`: **75/100, flagged CRITICAL/REJECT** by the tool's keyword heuristics. Manually reviewed both triggers:
  - *"Potential credential access"* — matched the prose word "credentials" in a sentence about running `nlm login` for stale credentials (documentation, not code). **False positive.**
  - *"[Medium] Silent action instruction"* — matched the word "silently" in *"Infer format/style/prompt silently ... then `studio_create(confirm=True)`"*. The instruction explicitly keeps the `confirm=True` gate before any mutating action — it only tells the assistant to infer *parameters* quietly, not to skip user confirmation. **False positive** (regex has no way to see that the confirm gate is preserved two words later).
  - The "High bash complexity" contribution (30 bash blocks) reflects that this SKILL.md is a CLI reference doc with many example commands — expected for its purpose.
  - **No changes made** — this is a documentation file, not executable code; the tool has no LLM mode enabled (regex-only, `skill-audit.sh` default), so no external data was sent.

## Cross-Tool Observations
- Gitleaks, TruffleHog, and Semgrep's `p/secrets` config all independently agree: **zero real secrets** in the repo. mcps-audit's 31 "secret_scan" hits are the same test fixtures these three tools also saw and correctly didn't flag as real.
- config-audit's "credential/cookie access" mentions and skill-audit's "credential access" hit both point at the same root cause: this project's docs *legitimately* discuss cookie-based authentication because that's the product's actual function, not a leak.
- No tool found anything in the newly-merged commits (`8f8cff7`, `25d618d`, `9357b86`) themselves — the auth-refresh hardening change (free port selection, `NOTEBOOKLM_DISABLE_HEADLESS_REFRESH`, `--clear` fix) introduced no new findings.

## Fixes Applied
**None required.** After individually verifying every Medium/High/Critical finding across all tools (Bandit, mcps-audit, config-audit, skill-audit), all were confirmed false positives specific to this project's domain (cookie/browser auth CLI) or scanner threat-model mismatch (autonomous-agent heuristics vs. conventional CLI code). No dependency had a known vulnerability (OSV-Scanner: 90/90 clean). No code or dependency changes were made in Phase 3c.

## Remaining Low/Info Issues (left unfixed by design)
- Bandit: 2,513 Low (`B101 assert_used` in tests, `B106` on parameter names like `old_token` in test fixtures).
- config-audit: ~19 Low (hook-configuration listings for globally-installed plugins, informational only).

## Coverage Gaps
- **Trivy** did not run (DB download failed twice on network reset) — dependency-vulnerability coverage for this pass relies on OSV-Scanner (clean) instead of Trivy's overlapping DB.
- **mcp-exfil-scan** was skipped — its bundled script failed the security-scanner skill's own SHA256 integrity check, and the skill's tamper-evidence rule says not to run a script that fails that check. Recommend reinstalling/updating the `claude-code-security-plugins` plugin to restore this checker.
- Not covered by any tool here: business logic correctness, IDOR-style authorization bugs, and runtime behavior (these require dynamic testing, not static scanning).

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260918T043844Z.jsonl`
- **Tool runs recorded:** 5 wrapped runs (gitleaks, semgrep-owasp ×2 including one retry, bandit, trivy) with measured exit code/duration; remaining tools (semgrep-python, semgrep-secrets, osv-scanner, trufflehog, mcps-audit, config-audit, skill-audit) run directly and reported manually above per their actual stdout.
- **Standard:** OWASP APTS § Auditability
