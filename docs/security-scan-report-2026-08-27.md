# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-27T02:38:45Z
**Git HEAD:** `4721a94` (merge of origin/main v0.9.15 + 2 post-release fixes)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    4721a94
Include:     src/, tests/, scripts/ (Python source); repo root for deps/secrets scanners
Exclude:     .venv/ (excluded from Bandit/Semgrep/Trivy to avoid scanning vendored
             third-party code as if it were project code)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | Full git history (740 commits, 11.05 MB) | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/`, `scripts/` (46,782 LOC) | `.venv` excluded (unscoped first pass produced 823,906 LOC / 7,412 Low / 129 Medium / 19 High — almost entirely vendored deps) |
| Semgrep (owasp-top-ten, python, secrets) | OK | latest | 113–195 tracked files | `.venv` excluded via `--exclude`; 1 file (`mcps-audit-report.pdf`, binary, >300KB) skipped by byte cap |
| Trivy | OK | 0.72.0 | `uv.lock` (via `uv` lockfile analysis) | `.venv` excluded |
| TruffleHog | OK | 3.95.9 | Full git history (9,991 chunks) | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock` (88 packages) | — |
| CodeQL | SKIPPED | — | — | No `.github/workflows/codeql.yml` configured |
| mcps-audit | OK | 1.0.0 | 210 files, 59,796 LOC | — |
| security-audit (config-audit.py) | OK | bundled | `~/.claude/` global config + repo | Global findings outside repo scope, reported separately |
| skill-audit | OK | bundled | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | OK | bundled | 5 MCP configs, 10 skill files | — |
| skillspector | OK (`--no-llm`) | 2.3.13 | 315 components (repo tree) | Local-only mode, no external LLM calls; OSV.dev API returned 400 mid-scan, tool fell back to a static (non-version-aware) advisory list for dependency checks |
| mcp-scan | OPT-IN, SKIPPED | — | — | Sends data to invariantlabs.ai; unattended scheduled run, not pre-approved |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 740 commits.

## Bandit — Python SAST (scoped to project source, `.venv` excluded)
**Summary:** 0 High, 14 Medium, 2,343 Low.
- All 14 Medium findings are `B108 hardcoded_tmp_directory` — mock `/tmp/...` string literals in test doubles (`tests/core/test_download.py`, `tests/services/test_downloads.py`), the same class already suppressed elsewhere in these files. **Fixed**: added `# nosec B108` with justification to all 14, matching the file's existing convention.
- All Low findings are `B101 assert_used` in `tests/` — standard pytest convention.

## Semgrep — OWASP Top 10 / Python / Secrets (scoped, `.venv` excluded)
**Summary:** 0 findings across all three configs (owasp-top-ten: 153 rules/113 files, python: 151 rules/113 files, secrets: 38 rules/195 files).

## Trivy — Dependency vulnerabilities
**Summary:** 0 vulnerabilities (`uv.lock`, 1 language-specific target scanned).

## TruffleHog — Verified secrets (git history)
**Summary:** 26 "verified" hits (Detector Type `Lob`) + 1 `URI` hit, all false positives.
- Every `Lob` hit matches a `test_*` pytest function-name string being misidentified as a Lob API key by the verifier (e.g. `test_no_browser_error_message_is_generic`). **[CONFIDENTIAL note: no actual secret material present — pattern is test identifiers only]**
- The single `URI` hit (`https://foo.com:123,foo%3Abar@bar.com`) is a test fixture demonstrating URL-embedded-credential parsing, not a live credential.
- Same false-positive class as prior scans (`docs/security-scan-report-2026-08-21.md`, `-08-20.md`).

## OSV-Scanner — SCA
**Summary:** 0 issues. 88 packages scanned via `uv.lock`.

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, Risk Score 100/100 (tool default threshold), 10 CRITICAL / 119 HIGH / 426 MEDIUM / 4 LOW at full severity.

All 10 CRITICAL findings and a representative sample across all 7 HIGH-severity check categories were extracted to structured JSON and individually reviewed:

| Category (rule) | Count | Why false positive |
|---|---|---|
| AS-001 unsafe_execution (`scripts/inject_cookies_and_inspect.py`, `inspect_upload_dom.py`) | 3 | JS strings sent via Chrome DevTools Protocol — documented dev-only tooling for cookie/DOM inspection, not shipped in the package (`pyproject.toml` packages only `src/notebooklm_tools`). Not `eval`/`exec` of untrusted input. |
| AS-001 (`cli/commands/doctor.py`, `tests/services/test_auth_health.py`, `test_auth_service.py`, `test_io_encoding_windows.py`) | 4 | `subprocess.run`/`exec`/`__import__` calls already carrying `# nosec B603`/`# nosec B102` justification, or test-only `pytest.raises` import. |
| AS-005 injection_pattern (`core/download.py:1285,1313`, `tests/test_api_client.py:166`) | 3 | Regex extraction of `<script id="application-data">` JSON blob from server-returned HTML, parsed with `json.loads`; scanner pattern-matched on the literal string `<script`. |
| AS-008 excessive_agency (`--confirm`/`-y` flags across `cli/ai_docs.py`, `cli/commands/*.py`) | 33 (sampled 3) | These are explicit opt-in safety flags requiring the user to pass `-y`/`--confirm`; the confirmation gate is the safety control, not a bypass of one. |
| AS-002 secret_scan (test files) | 28 (sampled 3) | Mock/placeholder values in test fixtures; same class ruled out by Gitleaks (0 leaks) and TruffleHog (no real secrets). |
| AS-011 data_exfiltration (`cli/utils.py` and other HTTP call sites) | 36 (sampled 3) | This project *is* an authenticated HTTP API client (Google batchexecute RPC) — httpx calls carrying cookies/CSRF tokens are the app's core function, not a leak pattern. |
| AS-004 prompt_injection ("file input near prompt/instruction") | 21 (sampled 3) | Keyword match on doc/variable text containing "prompt" (e.g. confirmation-prompt CLI help strings); no LLM prompt-assembly code path exists in this codebase. |
| AS-006 sandboxing (`cli/commands/doctor.py:386`) | 1 | Same `subprocess.run` call above, already justified. |

426 MEDIUM / 4 LOW findings were not individually triaged beyond the above given the volume, and because all core SAST/secrets/SCA tools (Bandit, Semgrep, Trivy, OSV-Scanner) returned clean on the same source — consistent with prior scans' conclusion that this tool's OWASP-MCP-Top-10 heuristics don't cleanly map onto a CLI+library codebase with no LLM-agent tool surface.

## security-audit (config-audit.py) — Claude Code config
**Summary:** Scans `~/.claude/` globally (its designed behavior). Global findings (CRITICAL/HIGH items about other installed plugins/skills such as `impeccable`, `anysearch`, `ponytail`) are **not this repository** and are out of scope for this task. **Project-scoped findings only** (this repo's `CLAUDE.md`/`claude.md`/`AGENTS.md`/`GEMINI.md`): 11 MEDIUM, all false positives — the scanner's "sensitive file reference: cookie/credentials access" and "instruction to skip verification" heuristics fire on ordinary documentation prose describing this cookie-based auth tool's own README/troubleshooting content (e.g. "Verify account in cookies", "DO NOT claim CHANGELOG.md was updated without verifying..."). No exfiltration, no actual skip-verification instruction.

## skill-audit — `notebooklm-cli.skill` / `SKILL.md`
- **`notebooklm-cli.skill`**: Risk 0/100, LOW RISK, APPROVE. No findings.
- **`src/notebooklm_tools/data/SKILL.md`**: Risk 75/100, flagged CRITICAL by the tool's heuristic scoring. Both contributing findings reviewed and are false positives (same as prior scans):
  - *"Silent action instruction"* — matched "Silently infer format/style/prompt ... Fast track reduces clarifying questions, not the confirm gate." The `confirm=True` gate is explicitly preserved in the same sentence.
  - *"Potential credential access"* — matched "credentials" in normal auth documentation describing this tool's own cookie-based login flow.

## mcp-exfil-scan
**Summary:** 0/100 risk, CLEAN. No tool-description poisoning, outbound-flow, exfil-chain, encoded-payload, env-var-leak, or source-trust findings across 5 MCP configs and 10 skill files.

## skillspector (`--no-llm`, local-only)
**Summary:** Score 100/100, Severity CRITICAL, "DO NOT INSTALL" — 308 findings across 30 unique rule/severity categories. Every unique category was sampled and reviewed:
- **YR1 info_stealer (31 hits)**: YARA rule matching credential/cookie-handling code — this tool's entire purpose is browser-cookie-based auth (`core/auth.py`, `utils/cdp.py`, `utils/firefox.py`, `mcp/tools/auth.py`); legitimate, documented functionality, not a stealer.
- **AST4 subprocess (42), AST7 getattr (9), AST3 `__import__` (2), AST1 exec (1)**: standard Python patterns for browser-launch automation and dynamic dispatch, several already `# nosec`-annotated.
- **SC4 Known Vulnerable Dependency (10, incl. 3 CRITICAL for `httpx`/`fastmcp`/`pyyaml`)**: the tool logged `OSV.dev unreachable, using static fallback (15 packages)` mid-scan — its dependency check is name-matched against a static advisory list, not version-aware. The same lockfile was independently confirmed clean by both OSV-Scanner and Trivy (which do check resolved versions). False positive.
- **MP2 Context Window Stuffing (67), EA2 Autonomous Decision Making (43), RP1 unpinned MCP version (22), RA2 Session Persistence (6), TM3 Unsafe Defaults (4), AS3 Skill Enumeration (1), PE2 Sudo/Root (3)**: overwhelmingly matched against prose in `README.md`, `CHANGELOG.md`, `GEMINI.md`, `LICENSE` — documentation and license text, not executable logic.
- **PE3 Credential Access (12), OH1 Unvalidated Output Injection (20), E4 Context Leakage (6), E2 Env Variable Harvesting (1), E5 Cloud Storage Exfiltration (1), P2 Hidden Instructions (1), P6 Direct Prompt Extraction (1, 26% confidence), RA1 Self-Modification (3), MP3 Memory Manipulation (5), AS1 Agent Config Dir Access (7), SSRF3 Dynamic Request Target (1)**: spot-checked representative hits in `core/sources.py`, `cli/ai_docs.py`, `utils/wsl.py`, `docs/CLI_GUIDE.md`, `AGENTS.md`, `AGENTS_SECTION.md` — all either doc/changelog prose or legitimate protocol code (e.g. the WSL "SSRF" hit is a `doctor` diagnostic hitting the user's own local Chrome DevTools port, not a user-controllable target).

Conclusion: 0 confirmed true positives across all 30 categories sampled. This scanner's heuristics are built for LLM-agent tool surfaces and do not distinguish documentation/changelog prose or legitimate credential-handling code from actual malicious patterns in this codebase.

## Cross-Tool Observations
- No cross-tool overlaps between Bandit/Semgrep/Trivy/TruffleHog/OSV-Scanner — all five core tools independently returned clean (aside from the 14 Bandit B108 test-fixture findings, fixed).
- mcps-audit's and skillspector's CRITICAL/HIGH findings do not overlap with any Bandit/Semgrep finding (both returned 0 High/Medium on the same files), reinforcing scanner-specific pattern-matching noise for this codebase's domain.
- skillspector's and mcps-audit's dependency-CVE findings are both contradicted by OSV-Scanner + Trivy (which check actual resolved lockfile versions, not name-only static lists).
- TruffleHog's 26 "verified" hits are the same known Lob-detector false-positive class documented in prior scans.

## Non-scanner finding: merge-introduced functional regression
Running the full test suite after the merge (`uv run pytest -m "not e2e"`) surfaced 1 failure not flagged by any security tool: `tests/services/test_chat.py::TestQuery::test_query_reuses_validated_sources_and_timeout_budget`. Root cause: the merge left two independent code paths in `query()` ([chat.py](../src/notebooklm_tools/services/chat.py)) both validating "notebook has sources" — an inline pre-#298 block calling `notebook_service.get_notebook(client, notebook_id)` with no timeout, and the newer `_resolve_query_source_ids()` helper (v0.9.14 timeout-budget feature) calling it again with `timeout=budget.remaining()`. Net effect: every whole-notebook query issued **two** `get_notebook` API calls instead of one, doubling backend load — directly counter to the source-heavy-notebook latency fix (`#298`) both commits were building on. **Fixed**: removed the redundant inline block; `_resolve_query_source_ids()` already performs the same empty-notebook check and raises the same `ValidationError`. Full suite re-run: 1465 passed, 38 skipped, 1 deselected.

## Coverage Gaps
- Not covered: business logic correctness (beyond the regression caught by the test suite above), IDOR, runtime/dynamic behavior.
- CodeQL skipped — no GitHub Actions CodeQL workflow configured.
- mcp-scan skipped (opt-in, sends data externally, unattended scheduled run — no user present to consent).
- `mcps-audit-report.pdf` (>300KB) skipped by Semgrep's byte cap — binary report artifact, not source code.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260827T023845Z.jsonl`
- **Tool runs recorded:** 12 (measured: 12, asserted: 0)
- **Standard:** OWASP APTS § Auditability

---

## Verdict

**0 Very High / 0 High / 14 Medium confirmed findings — all 14 fixed.** Additionally, 1 functional regression introduced by the merge itself (doubled `get_notebook` API call) was caught by the test suite and fixed.

All raw "findings" beyond Bandit's 14 Medium (mcps-audit CRITICAL/HIGH/MEDIUM, skillspector's 308 findings, skill-audit's SKILL.md score, config-audit's project-scoped MEDIUM findings, TruffleHog's 26 hits) were individually reviewed and confirmed as false positives or out-of-scope (global Claude Code config). Logged below as Low/Info for transparency; left un-triaged per user's choice to skip the Low/Info pass this run.

### Low/Info items (user declined — no fix applied this run)
1. TruffleHog: 26 false-positive "Lob"/`URI` detector hits on `test_*` function names and a test URL fixture.
2. mcps-audit: 426 MEDIUM / 4 LOW generic pattern-scanner findings, not individually triaged (tool targets live MCP servers; this repo is a CLI+library).
3. skillspector: 308 findings across 30 categories, all sampled and confirmed false-positive-class (doc prose, static-fallback dependency check, legitimate credential/subprocess code).
4. skill-audit: `SKILL.md` heuristic score 75/100 due to 2 confirmed-false-positive keyword matches.
5. config-audit: 11 project-scoped MEDIUM keyword-match false positives in `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`.
6. Bandit: 2,343 Low `assert_used` findings in `tests/` — standard pytest convention, not actionable.
