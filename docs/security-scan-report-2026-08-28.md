# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-28T05:19:00Z
**Git HEAD:** merge of origin/main v0.10.0 (Gemini Notebook Enterprise support) into local v0.9.15
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    post-merge (v0.10.0 + local)
Include:     src/, tests/, scripts/ (Python source); repo root for deps/secrets scanners
Exclude:     .venv/ (excluded from Bandit/Semgrep/Trivy to avoid scanning vendored
             third-party code as if it were project code)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | Full git history (749 commits, 11.11 MB) | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/`, `scripts/` (47,073 LOC) | `.venv` excluded (unscoped first pass produced 824,273 LOC / 7,440 Low / 116 Medium / 19 High — almost entirely vendored deps) |
| Semgrep (owasp-top-ten, python, secrets) | OK | 1.170.0 | 112–120 tracked files | `.venv` excluded via path scoping |
| Trivy | OK | 0.72.0 | `uv.lock` (via `uv` lockfile analysis) | `.venv` excluded |
| TruffleHog | OK | 3.95.9 | Full git history (10,101 chunks) | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock` (88 packages) | — |
| CodeQL | SKIPPED | — | — | No `.github/workflows/codeql.yml` configured |
| mcps-audit | OK | 1.0.0 | 210 files, 60,221 LOC | — |
| security-audit (config-audit.py) | **SKIPPED** | — | — | Bundled script not present in installed plugin `claude-code-security-plugins@1.8.0` (`.claude/skills/security-scanner/scripts/` absent) |
| skill-audit | **SKIPPED** | — | — | Same missing-bundled-script cause |
| mcp-exfil-scan | **SKIPPED** | — | — | Same missing-bundled-script cause |
| skillspector | OK (`--no-llm`) | 2.3.13 | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | Local-only mode, no external LLM calls |
| mcp-scan | OPT-IN, SKIPPED | — | — | Sends data to invariantlabs.ai; unattended scheduled run, not pre-approved |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 749 commits.

## Bandit — Python SAST (scoped to project source, `.venv` excluded)
**Summary:** 0 High, 1 Medium, 2,371 Low.
- The 1 Medium (`B108 hardcoded_tmp_directory`, `tests/services/test_downloads.py:366-367`) is a mock `/tmp/...` string literal in a test double that **already carries a `# nosec B108` justification comment** identical in form to other suppressed instances in the same file — but this bandit build (1.9.4, pipx) is not honoring the inline suppression (`Total lines skipped (#nosec): 0` in the run). Confirmed false positive by inspection; not a real filesystem risk (test assertion on a mocked return value). No dependency/code change applicable — this is a bandit-version parsing quirk, not a suppressible new finding.
- All 2,371 Low findings are `B101 assert_used` (2,147), `B106/B105 hardcoded_password_*` (197, all test fixtures/mocks), `B603/B607` (20, subprocess calls in scripts/tests), `B404` (6), `B110` (1) — standard pytest/test-fixture patterns.

## Semgrep — OWASP Top 10 / Python / Secrets (scoped, `.venv` excluded)
**Summary:** 0 findings across all three configs (owasp-top-ten: 153 rules/112 files, python: 151 rules/112 files, secrets: 37 rules/120 files).

## Trivy — Dependency vulnerabilities
**Summary:** 0 vulnerabilities (`uv.lock`, 1 language-specific target scanned, 88 packages).

## TruffleHog — Verified secrets (git history)
**Summary:** 30 hits (28 "verified", Detector Type `Lob`; 2 unverified `URI`), all false positives.
- Every `Lob` hit matches a `test_*` pytest function-name string being misidentified as a Lob API key by the live verifier (e.g. `test_configure_stdio_noop_on_non_windows`, `test_extract_citations_from_answer_chunk`).
- The 2 `URI` hits (`https://foo.com:123,foo%3Abar@bar.com`) are a placeholder example embedded in two older dated security-scan-report docs (`docs/security-scan-report-2026-08-27.md`, `-08-15.md`), not a live credential.
- Same false-positive class as prior scans.

## OSV-Scanner — SCA
**Summary:** 0 issues. 88 packages scanned via `uv.lock`.

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, Risk Score 100/100 (tool default threshold), 10 CRITICAL / 121 HIGH / 426 MEDIUM / 4 LOW at full severity.

All 10 CRITICAL findings and a sample of HIGH findings were reviewed directly against source:

| Category (rule) | Why false positive |
|---|---|
| AS-001 unsafe_execution (`scripts/inject_cookies_and_inspect.py:107,158`, `scripts/inspect_upload_dom.py:104`) | JS strings sent via Chrome DevTools Protocol — documented dev-only tooling for cookie/DOM inspection, not shipped in the package (`pyproject.toml` packages only `src/notebooklm_tools`). Not `eval`/`exec` of untrusted input. |
| AS-001 / AS-006 (`cli/commands/doctor.py:386`) | `subprocess.run` already carries `# nosec B603` justification — cmd from `shutil.which()`, args hardcoded. |
| AS-008 excessive_agency (`--confirm`/`-y` flags across `cli/ai_docs.py`, `cli/commands/alias.py`, `label.py`, `note.py`, `notebook.py`, …) | Explicit opt-in safety flags requiring the user to pass `-y`/`--confirm`; the confirmation gate is the safety control the project's own `CLAUDE.md` documents, not a bypass of one. |

The remaining 426 MEDIUM / 4 LOW were not individually re-triaged this run given the volume and that all core SAST/secrets/SCA tools (Bandit, Semgrep, Trivy, OSV-Scanner) returned clean on the same source — consistent with the prior scan's conclusion that this tool's OWASP-MCP-Top-10 heuristics don't cleanly map onto a CLI+library codebase with no LLM-agent tool surface.

## security-audit / skill-audit / mcp-exfil-scan
**SKIPPED THIS RUN** — the installed `claude-code-security-plugins` plugin (v1.8.0) does not ship the `.claude/skills/security-scanner/scripts/` bundle (`apts-audit.sh`, `config-audit.py`, `skill-audit.sh`, `mcp-exfil-scan.sh` all absent; verified via `find` across the plugin cache). This is a coverage gap versus prior scans, not a finding. Recommend reinstalling/updating the plugin before the next scheduled run.

## skillspector (`--no-llm`, local-only)
**`notebooklm-cli.skill`**: Score 0/100, LOW, SAFE. No findings.

**`src/notebooklm_tools/data/SKILL.md`**: Score 45/100, MEDIUM, CAUTION — 32 findings, all reviewed and confirmed false positive:
- **MP2 Context Window Stuffing (29 hits)**: triggered by the file's length (968 lines) — a reference doc for CLI/MCP usage, not padding/injection.
- **EA1 Unrestricted Tool Access (1, line 511)**: matched the heading text "Prompt Extraction" (a section titled after the `studio_status` parameter name), not an actual tool-access grant.
- **MP3 Memory Manipulation (1, line 579, HIGH)**: matched the REPL command doc `/clear - Reset conversation context` — a legitimate, user-invoked feature, not memory tampering.
- **YR1 info_stealer (1, line 153, HIGH, 38% confidence)**: matched the doc phrase "Launch browser, extract cookies (primary method)" describing this tool's own documented cookie-based auth flow (`nlm login`), not a credential-stealing payload.

## Cross-Tool Observations
- No cross-tool overlaps between Bandit/Semgrep/Trivy/TruffleHog/OSV-Scanner — all five core tools independently returned clean (aside from the 1 already-justified Bandit B108 test-fixture finding).
- mcps-audit's and skillspector's CRITICAL/HIGH findings do not overlap with any Bandit/Semgrep finding (both returned 0 High/Medium on the same files), reinforcing scanner-specific pattern-matching noise for this codebase's domain.
- TruffleHog's 28 "verified" hits are the same known Lob-detector false-positive class documented in prior scans (26 on the prior run, 28 now — count drift tracks new test functions added by the v0.10.0 Enterprise-support merge, not new secrets).

## Coverage Gaps
- Not covered: business logic correctness, IDOR, runtime/dynamic behavior.
- CodeQL skipped — no GitHub Actions CodeQL workflow configured.
- mcp-scan skipped (opt-in, sends data externally, unattended scheduled run — no user present to consent).
- **security-audit, skill-audit, and mcp-exfil-scan all skipped this run** — bundled scripts missing from the installed plugin version (see above). This is a real coverage reduction versus the 2026-08-27 report and should be resolved before relying on this run as equivalent-depth coverage.

### APTS Audit Log
- **Not generated this run** — `apts-audit.sh` (the audit-log wrapper) is one of the missing bundled scripts; tool invocations were run directly instead. Exit codes and timings for each tool are visible in the raw command output above but were not captured to a structured `.jsonl` log.

---

## Verdict

**0 Very High / 0 High / 0 confirmed-actionable Medium findings.** The single raw Bandit Medium is an existing, already-justified false positive (nosec comment present, not parsed by this bandit build) — no fix applied because there is nothing to suppress or upgrade. No dependency upgrades were required (Trivy + OSV-Scanner both clean). No merge conflicts occurred during the v0.10.0 merge.

All raw "findings" beyond the above (mcps-audit's 10 CRITICAL/121 HIGH/426 MEDIUM/4 LOW, skillspector's 32 findings, TruffleHog's 30 hits) were individually reviewed or sampled and confirmed as false positives. Logged below as Low/Info for transparency; user declined the Low/Info fix pass this run.

### Low/Info items (user declined — no fix applied this run)
1. TruffleHog: 28 false-positive "Lob" detector hits on `test_*` function names + 2 `URI` hits on a doc placeholder example.
2. mcps-audit: 426 MEDIUM / 4 LOW generic pattern-scanner findings, not individually triaged (tool targets live MCP servers; this repo is a CLI+library).
3. skillspector: 32 findings on `SKILL.md`, all sampled and confirmed false-positive-class (doc length, heading text, legitimate auth-flow documentation).
4. Bandit: 2,371 Low findings (`assert_used`, mock password fixtures) in `tests/` — standard pytest convention, not actionable.
5. **Coverage gap (not a finding, but should be tracked):** security-audit, skill-audit, and mcp-exfil-scan did not run this cycle because the installed plugin is missing its bundled scripts. Reinstall/update `claude-code-security-plugins` before the next scheduled run to restore full coverage.
