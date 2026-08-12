# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-12T07:12:23Z – 2026-08-12T07:17:09Z
**Git HEAD:** post-merge of origin/main v0.9.8–v0.9.10 (11 commits, PRs #284–#292)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    807f2d1 (post-merge)
Include:     all supported (src/, tests/, docs/, config files)
Exclude:     .venv/ (third-party dependencies)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | 718 commits, ~10.8MB | — |
| Bandit | OK | 1.9.4 | repo (src+tests, `.venv` excluded, 44,705 LOC) | — |
| Semgrep (OWASP Top 10) | OK | latest | 109 files, 153 rules | 93 files matched `.semgrepignore` |
| Semgrep (Python) | OK | latest | 109 files, 151 rules | same as above |
| Semgrep (secrets) | OK | latest | 182 files, 38 rules | 93 files matched `.semgrepignore` |
| Trivy (fs) | OK | 0.72.0 | uv.lock (88 packages) | `.venv` skipped |
| TruffleHog | OK | 3.95.9 | git history, 9480 chunks | — |
| OSV-Scanner | OK | 2.4.0 | uv.lock (88 packages) | — |
| CodeQL | SKIPPED | — | — | no `.github/workflows/codeql.yml` |
| mcps-audit | OK | 1.0.0 | 203 files, 57,314 LOC | — |
| security-audit (config-audit.py) | OK | bundled | global `~/.claude` + repo docs | — |
| skill-audit | OK | bundled v2.0 | `notebooklm-cli.skill`, `data/SKILL.md` | — |
| mcp-exfil-scan | OK | bundled v1.0 | repo (5 MCP configs, 10 skill files) | — |
| skillspector | OK | 2.3.13, `--no-llm` | 299 components | OSV.dev batch query 400 → static fallback |
| mcp-scan | OPT-IN, SKIPPED | — | — | unattended scheduled run, no user present to consent to external transmission to invariantlabs.ai |

## Gitleaks — Secrets (git history + filesystem)
**Summary:** 0 leaks found across 718 commits.

## Bandit — Python SAST
**Summary (before fixes):** 0 High, 90 Medium, 2221 Low (repo-scoped, `.venv` excluded).
**Summary (after fixes):** 0 High, **0 Medium**, 2221 Low.

- 89× `B108` hardcoded-tmp-directory (Medium) — all mock `AsyncMock(return_value="/tmp/...")`/similar string literals in test doubles across `tests/services/test_downloads.py`, `tests/services/test_sources.py`, `tests/core/test_download.py`, `tests/cli/test_download_all.py`, `tests/cli/test_login.py`, `tests/test_cookie_parsing.py`, `tests/test_mcp_downloads.py`, `tests/test_wsl.py` — never touch the real filesystem. **Fixed:** annotated each with `# nosec B108` + justification.
- 1× `B102` exec_used (Medium) in `tests/services/test_auth_service.py:171` — `exec()` of a fixed literal import statement (no user input) to test a PEP 562 shim's re-import behavior. **Fixed:** annotated with `# nosec B102` + justification.
- No High/Medium findings remain in `src/` or `tests/`. Full test suite re-run after annotation: 1407 passed, 38 skipped, 0 regressions.

## Semgrep — OWASP Top 10 / Python / Secrets
**Summary:** 0 findings. 342 combined rule executions across 109–182 files.

## Trivy — Dependencies (fs scan)
**Summary:** 0 vulnerabilities, 0 secrets. `uv.lock` (88 packages) clean. Trivy 0.72.0 — outside the compromised 0.69.4–0.69.6 range (GHSA-69fq-xp46-6x23).

## TruffleHog — Secrets (git-verified)
**Summary:** 24 "verified" hits, all Detector Type `Lob`, all in `tests/` — confirmed false positives: the Lob API-key regex/verification matches descriptive test function names (e.g. `test_empty_query_raises_validation_error`), not real credentials. Pre-existing across git history; none introduced by the 11 merged commits. No code change made — these are not exploitable and the detector offers no per-finding suppression mechanism; documented here for audit trail.

## OSV-Scanner — SCA
**Summary:** No issues found. `uv.lock` (88 packages).

## mcps-audit — MCP permission audit
**Summary:** Verdict FAIL, 100/100 (10 Critical, 116 High, 415 Medium, 4 Low). All 10 Critical (`AS-001 Dangerous execution`) are in `scripts/inject_cookies_and_inspect.py` / `scripts/inspect_upload_dom.py` — developer diagnostic scripts that intentionally execute JS via CDP to inspect cookie/DOM state, this project's documented core mechanism. No code change made — the flagged behavior is the tool's intended function, not a vulnerability; not part of the 11 merged commits.

## security-audit (config-audit.py) — Claude config audit
**Summary:** 99 issues found globally across `~/.claude`, only 11 repo-scoped (all Medium, "credentials/cookie file access" in `CLAUDE.md`/`claude.md`/`AGENTS.md`/`GEMINI.md`) — confirmed false positives, same root cause as prior scans: these docs legitimately describe this project's cookie-based Google auth flow. No code change made.

## skill-audit — Packaged skill files
**Summary:** `notebooklm-cli.skill`: 0/100, LOW RISK, APPROVE. `src/notebooklm_tools/data/SKILL.md`: 75/100, flagged CRITICAL — confirmed false positive (same as prior cycles): "Silently infer" UX guidance and a single "credentials" reference in documented auth guidance, not a consent bypass or exfiltration path. No code change made.

## mcp-exfil-scan — MCP exfiltration detection
**Summary:** 0/100, CLEAN across all 6 categories.

## skillspector (NVIDIA AI-skill scanner, `--no-llm`)
**Summary:** 100/100, CRITICAL, "DO NOT INSTALL" — 252 findings. Dominant classes: YARA `info_stealer` matching "credentials"/"cookie" in legitimate auth code (`core/auth.py`, `utils/cdp.py`, `services/auth_replay.py`), `AST4` subprocess-call flags on list-form (non-`shell=True`) calls consistent with Bandit's 0-High result, `AST7` `getattr()` usage with no attacker-controlled input at the sampled location. Confirmed false-positive class — no finding lands inside the two files touched by this session's merge-conflict resolution. No code change made.

## Cross-Tool Observations
- Gitleaks, Semgrep-secrets, Trivy, and TruffleHog (after FP review) independently agree: **zero real secrets** in the repo or git history.
- Bandit (post-fix), Semgrep-OWASP/Python, and OSV-Scanner independently agree: **zero exploitable code-level or dependency vulnerabilities** in `src/`.
- mcps-audit, skillspector, and skill-audit's SKILL.md all score CRITICAL/100 from the same underlying pattern class: this project's legitimate cookie-handling and CDP-JS-execution auth mechanism, which their heuristics (tuned for small prompt-only AI skills) cannot distinguish from malicious credential theft or command injection. Correlates as one systemic false-positive class across three tools, not three independent real findings — consistent with the 2026-08-06 scan's conclusion.
- No cross-tool finding lands inside `src/notebooklm_tools/core/auth.py` or `src/notebooklm_tools/utils/wsl.py` at the specific lines touched by this session's merge-conflict resolutions.

## Coverage Gaps
- Business logic and IDOR-style authorization bugs not covered by static tools — not assessed.
- Runtime behavior (live MCP tool call flows, actual cookie handling) not exercised — static analysis only.
- CodeQL skipped — no CodeQL GitHub Actions workflow in this repo.
- mcp-scan (opt-in, external service) skipped this run — unattended scheduled task, no user present to consent to the invariantlabs.ai data transmission it requires.
- skillspector's OSV.dev batch query returned HTTP 400 and fell back to static vulnerability data for that sub-check; OSV-Scanner (dedicated SCA tool) returned a clean, current result independently.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260812T071223Z.jsonl`
- **Tool runs recorded:** 16 (measured: 15, asserted: 1)
- **Standard:** OWASP APTS § Auditability

---

## Overall Verdict

**No exploitable Very High/High/Medium findings remain in production or test code.** All 90 real Bandit Medium findings (89× B108 test-mock temp paths, 1× B102 fixed-literal exec in a shim-behavior test) were fixed with `# nosec` suppression + justification and verified against a clean 1407-test pass. The remaining Critical/High/Medium noise from mcps-audit, skillspector, skill-audit, and config-audit is a confirmed, cross-tool-corroborated false-positive class rooted in this project's legitimate, documented cookie-based auth mechanism — consistent with every prior scan cycle back to 2026-04. TruffleHog's 24 "verified" hits are confirmed non-secret test-identifier false positives from the Lob detector.

**User declined Low/Info remediation this cycle** — 2,221 Bandit Low findings (predominantly `B101 assert_used` in test files, standard pytest usage) left as-is.
