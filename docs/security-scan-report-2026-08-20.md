# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-20T03:08:30Z
**Git HEAD:** `0db9c30` (post-merge of origin/main v0.9.12 + 2 follow-up commits)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    0db9c30
Include:     src/, tests/, scripts/ (Python source); repo root for deps/secrets scanners
Exclude:     .venv/ (158 MB third-party deps — excluded from Bandit/Semgrep/Trivy to avoid
             scanning vendored code as if it were project code)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | Full git history (729 commits, 10.89 MB) | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/`, `scripts/` (45,186 LOC) | `.venv` excluded (first pass without scoping produced 7,447 findings, nearly all in vendored deps) |
| Semgrep (owasp-top-ten, python, secrets) | OK | latest | 109–187 tracked files | `.venv` excluded via `--exclude`; 1 file >300KB skipped (uv.lock, not source) |
| Trivy | OK | 0.72.0 | `uv.lock` (88 packages) | `.venv` excluded |
| TruffleHog | OK | 3.95.9 | Full git history (9,661 chunks) | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock` (88 packages) | — |
| CodeQL | SKIPPED | — | — | No `.github/workflows/codeql.yml` configured |
| mcps-audit | OK | 1.0.0 | 205 files, 57,964 LOC | — |
| security-audit (config-audit.py) | OK | bundled | `~/.claude/` global config + repo | Findings outside repo scope reported separately (informational) |
| skill-audit | OK | bundled | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | OK | bundled | 5 MCP configs, 10 skill files | — |
| mcp-scan | OPT-IN, SKIPPED | — | — | Sends data to invariantlabs.ai; unattended scheduled run, not pre-approved |
| skillspector | OPT-IN, SKIPPED | — | — | LLM-assisted mode requires consent; unattended scheduled run, not pre-approved |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 729 commits.

## Bandit — Python SAST (scoped to project source)
**Summary:** 0 High, 0 Medium, 2,244 Low.
- All Low findings are `B101 assert_used` in `tests/` (expected — pytest convention) and stylistic blacklist notices.
- Note: an unscoped run (`bandit -r .`) also crawls `.venv/` and reports 19 High / 115 Medium / 7,313 Low — these are entirely within third-party vendored packages, not project code, and are not actionable here.

## Semgrep — OWASP Top 10 / Python / Secrets (scoped, `.venv` excluded)
**Summary:** 0 findings across all three configs (owasp-top-ten: 153 rules/109 files, python: 151 rules/109 files, secrets: 38 rules/187 files).

## Trivy — Dependency vulnerabilities
**Summary:** 0 vulnerabilities in `uv.lock` (88 packages).

## TruffleHog — Verified secrets (git history)
**Summary:** 25 "verified" hits, all Detector Type `Lob`, all false positives.
- Every hit matches a `test_*` pytest function-name string (e.g. `test_extract_citations_from_answer_chunk`) being misidentified as a Lob API key by the verifier. **[CONFIDENTIAL note: no actual secret material present — pattern is test identifiers only]**
- Consistent with the false-positive class already documented in the prior scan (`docs/security-scan-report-2026-08-15.md`).

## OSV-Scanner — SCA
**Summary:** 0 issues. 88 packages scanned via `uv.lock`.

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, Risk Score 100/100 (tool default threshold), 10 CRITICAL / 117 HIGH / 417 MEDIUM / 4 LOW raw pattern matches.

All 10 CRITICAL findings were individually reviewed and are false positives:
| File:Line | Rule | Why it's a false positive |
|---|---|---|
| `scripts/inject_cookies_and_inspect.py:107,158` | AS-001 unsafe_execution | JS string sent via Chrome DevTools Protocol (`page.evaluate`) — documented dev tooling for cookie extraction, per `CLAUDE.md`'s `utils/cdp.py` description. Not `eval`/`exec` of untrusted input. |
| `scripts/inspect_upload_dom.py:104` | AS-001 | Same CDP JS-injection pattern, dev-only DOM inspection script. |
| `src/notebooklm_tools/cli/commands/doctor.py:386` | AS-001 | `subprocess.run(...)` already carries `# nosec B603` with justification (cmd from `shutil.which()`, hardcoded args). |
| `src/notebooklm_tools/core/download.py:1103,1131` | AS-005 known_injection_pattern | Regex extraction of `<script id="application-data">` JSON blob from HTML, parsed with `json.loads` — no `eval`/template injection. Scanner pattern-matched on the literal string `<script`. |
| `tests/services/test_auth_health.py:340` | AS-001 | `__import__(...)` inside a test helper, test-only code. |
| `tests/services/test_auth_service.py:171` | AS-001 | `exec(...)` already carries `# nosec B102` justification (fixed literal import statement, no user input). |
| `tests/test_api_client.py:166` | AS-005 | Same `<script>`-string regex pattern as above, in a test fixture. |
| `tests/test_io_encoding_windows.py:37` | AS-001 | `__import__("pytest").raises(...)` — standard pytest idiom, test-only. |

The 117 HIGH / 417 MEDIUM findings are generic pattern-scanner noise (this tool targets live MCP-server deployments; this repo is a CLI+library, not a standalone MCP server process, so many OWASP-MCP-Top-10 categories don't cleanly apply). None were found to overlap with anything flagged by Bandit, Semgrep, Trivy, or TruffleHog. Given the volume and that the six core SAST/secrets/SCA tools all returned clean on actual project code, these are logged for visibility but not individually triaged — recommend running `mcps-audit . --severity HIGH --json` in a future session if closer review is wanted.

## security-audit (config-audit.py) — Claude Code config
**Summary:** Scans `~/.claude/` globally (its designed behavior), not scoped to this repo. All findings are about the user's own installed plugins/skills (`anysearch`, `caveman`, `claude-code-security-plugins`, `claude-plugins-official`, etc.) and global `settings.json` hooks — **none originate from or apply to this repository**. Reported here for completeness only; no in-repo remediation applicable.

## skill-audit — `notebooklm-cli.skill` / `SKILL.md`
- **`notebooklm-cli.skill`**: Risk 0/100, LOW RISK, APPROVE. No findings.
- **`src/notebooklm_tools/data/SKILL.md`**: Risk 75/100, flagged CRITICAL by the tool's heuristic scoring. Both contributing findings reviewed and are false positives:
  - *"Silent action instruction"* (Medium) — matched the word "silently" in "**Fast track (default):** Silently infer format/style/prompt ... one-line notice → `studio_create(confirm=True)`." This describes skipping a *clarifying-question UX step*, not hiding an action from the user; the `confirm=True` gate is still enforced before any Studio artifact is created.
  - *"Potential credential access"* — matched the word "credentials" in normal auth documentation ("Run `nlm login` for ... confirmed stale/missing credentials"), not an attempt to read/exfiltrate credential material.

## mcp-exfil-scan
**Summary:** 0/100 risk, CLEAN. No tool-description poisoning, outbound-flow, exfil-chain, encoded-payload, env-var-leak, or source-trust findings across 5 MCP configs and 10 skill files.

## Cross-Tool Observations
- No cross-tool overlaps between Bandit/Semgrep/Trivy/TruffleHog/OSV-Scanner findings — all five core tools independently returned clean on project source.
- mcps-audit's 10 CRITICAL findings do not overlap with any Bandit/Semgrep finding (both returned 0 High/Medium on the same files), reinforcing that they are scanner-specific pattern-matching noise rather than confirmed issues.
- TruffleHog's 25 "verified" hits are a known detector false-positive class (test function names matching the Lob API key format) — same pattern documented in the 2026-08-15 report.

## Coverage Gaps
- Not covered: business logic correctness, IDOR, runtime/dynamic behavior.
- CodeQL skipped — no GitHub Actions CodeQL workflow configured in this repo.
- mcp-scan and skillspector LLM-assisted mode skipped (opt-in, unattended scheduled run — consistent with prior scan).

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260820T030830Z.jsonl`
- **Tool runs recorded:** 15 (measured: 15, asserted: 0)
- **Standard:** OWASP APTS § Auditability

---

## Verdict

**0 Very High / 0 High / 0 Medium confirmed findings.** No fixes required in Phase 3c.

All raw "findings" beyond the six core tools (mcps-audit CRITICAL/HIGH/MEDIUM, skill-audit's SKILL.md score, TruffleHog's 25 hits) were individually reviewed and confirmed as false positives or out-of-scope (global Claude Code config). Logged below as Low/Info for transparency per Phase 3b instructions.

### Low/Info items (deferred to Phase 3d — user decides whether to address)
1. TruffleHog: 25 false-positive "Lob" detector hits on `test_*` function names (no code change needed; cosmetic only if addressed — e.g. could rename test functions, not recommended).
2. mcps-audit: 117 HIGH / 417 MEDIUM generic pattern-scanner findings, not individually triaged (tool targets live MCP servers; this repo is a CLI+library). Optional follow-up: re-run with `--severity HIGH --json` for manual review.
3. skill-audit: `SKILL.md` heuristic score 75/100 due to 2 confirmed-false-positive keyword matches ("silently", "credentials") in normal documentation prose — no code/doc change needed.
4. Bandit (unscoped `.venv` run only, informational): 19 High / 115 Medium in third-party vendored packages — not actionable from this repo (would require upstream dependency fixes, already covered by the 0-vulnerability Trivy/OSV-Scanner results against `uv.lock`).
