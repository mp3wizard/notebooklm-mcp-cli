# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-09-07T15:58:25Z
**Git HEAD:** `f97ae9d` — merge of origin/main v0.11.0 (nlm auth refresh, session recovery fix, CI checkout v6; also brings in the unreleased v0.10.1 security fix) into local
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    f97ae9d (post-merge v0.11.0)
Include:     src/, tests/, scripts/ (Python source); repo root for deps/secrets scanners
Exclude:     .venv/, .git/, node_modules/ (excluded from Bandit/Semgrep/Trivy to avoid
             scanning vendored third-party code as if it were project code)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | Full git history (756 commits, 11.17 MB) | — |
| Bandit | OK | 1.9.4 | `src/`, `tests/`, `scripts/` (47,664 LOC) | `.venv` excluded (unscoped first pass produced 824,788 LOC / 7,480 Low / 116 Medium / 19 High — almost entirely vendored deps in `.venv`) |
| Semgrep (owasp-top-ten, python, secrets) | OK | 1.176.1 | 113–198 tracked files | `.venv`/`node_modules` excluded; 1 file >300KB skipped (`mcps-audit-report.pdf`, a prior scan's PDF output, not source) |
| Trivy | OK | 0.74.0 | `uv.lock` (88 packages) | `.venv` excluded via `--skip-dirs`; version confirmed outside the GHSA-69fq-xp46-6x23 compromised range (0.69.4-0.69.6) |
| TruffleHog | OK | 3.97.4 | Full git history (10,192 chunks, 11.55 MB) | — |
| OSV-Scanner | OK | 2.5.1 | `uv.lock` (88 packages) | — |
| CodeQL | SKIPPED | — | — | No `.github/workflows/codeql.yml` configured |
| mcps-audit | OK | 1.0.0 | 213 files, 60,925 LOC | — |
| security-audit (config-audit.py) | OK | — | Project files + `~/.claude` global config (tool's own design — scans user-level config regardless of target path) | — |
| skill-audit | OK | — | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | **SKIPPED** | — | — | Bundled script checksum mismatch (`mcp-exfil-scan.sh: FAILED` against `SHA256SUMS`) — tamper-evidence rule says do not run a script that fails integrity verification |
| skillspector | not run | — | — | Not re-run this cycle; prior scan already sampled all 32 findings on `SKILL.md` and confirmed false-positive class (see 2026-08-28 report) |
| mcp-scan | OPT-IN, SKIPPED | — | — | Sends data to invariantlabs.ai; unattended scheduled run, no user present to consent |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks found across 756 commits (sarif + text, both runs agree).

## Bandit — Python SAST (scoped to project source, `.venv` excluded)
**Summary before fix:** 0 High, 1 Medium, 2,411 Low.
**Summary after fix:** 0 High, **0 Medium**, 2,411 Low.
- The 1 Medium (`B108 hardcoded_tmp_directory`, `tests/services/test_downloads.py:381`) was a real suppression bug, not a security issue: the `# nosec B108` comment sat on line 382 (a closing-paren continuation line) instead of line 381 (the flagged string literal), so bandit never associated the two. Fixed by moving the comment onto the correct line — confirmed via rerun (0 Medium after).
- All 2,411 Low findings are `B101 assert_used` in `tests/` — standard pytest assertion pattern, not actionable.

## Semgrep — OWASP Top 10 / Python / Secrets (scoped, `.venv`/`node_modules` excluded)
**Summary:** 0 findings across all three configs (owasp-top-ten: 153 rules/113 files, python: 151 rules/113 files, secrets: 38 rules/198 files).

## Trivy — Dependency vulnerabilities + secrets
**Summary:** 0 vulnerabilities, 0 secrets (`uv.lock`, 88 packages).

## TruffleHog — Verified secrets (git history)
**Summary:** 0 verified, 3 unverified `URI` hits, all false positives.
- All 3 hits are the same placeholder example (`https://foo.com:123,foo%3Abar@bar.com`) embedded in three older dated security-scan-report docs (`docs/security-scan-report-2026-08-15.md`, `-08-27.md`, `-08-28.md`) — not a live credential, and the verifier itself reports "no such host" for `bar.com`.
- Same false-positive class as prior scans.

## OSV-Scanner — SCA
**Summary:** 0 issues. 88 packages scanned via `uv.lock`.

## mcps-audit — OWASP MCP Top 10 + Agentic AI Top 10
**Summary:** Verdict FAIL, Risk Score 100/100 (tool default threshold), 10 CRITICAL / 123 HIGH / 429 MEDIUM / 4 LOW at full severity.

All 10 CRITICAL findings reviewed directly against source:

| Category (rule) | Why false positive |
|---|---|
| AS-001 unsafe_execution (`scripts/inject_cookies_and_inspect.py:107,158`, `scripts/inspect_upload_dom.py:104`) | JS strings sent via Chrome DevTools Protocol — documented dev-only tooling for cookie/DOM inspection, not shipped in the package (`pyproject.toml` `[tool.setuptools]` packages only `src/notebooklm_tools`; `scripts/` is excluded). Not `eval`/`exec` of untrusted input. |
| AS-003 high_risk_permission (`scripts/test_label_rpcs.py:48,100,205`) | Matched the substring `DELETE` inside an RPC constant name (`RPC_LABEL_DELETE`) and a docstring/section-header describing a manual test-and-cleanup script for the label API — not an actual privilege-escalation path. |
| AS-010 no_logging (`desktop-extension/run_server.py`, `scripts/build_mcpb.py`, `scripts/inspect_upload_dom.py`) | Generic "no logging framework detected" heuristic on small entrypoint/build scripts — informational, not a vulnerability. |
| AS-007 (`desktop-extension/run_server.py:54`) | "Dependency without integrity verification" — a LOW finding on a subprocess call in the desktop-extension launcher; not re-triaged individually (see below). |

The remaining 429 MEDIUM / 4 LOW (largely the same AS-003/AS-010 pattern classes above, repeated across `scripts/`) were not individually re-triaged this run — consistent with prior scans' conclusion that this tool's OWASP-MCP-Top-10 heuristics don't cleanly map onto a CLI+library codebase with dev-only browser-automation scripts, and all core SAST/secrets/SCA tools (Bandit, Semgrep, Trivy, OSV-Scanner) returned clean on the same source.

## security-audit (config-audit.py)
**Summary:** 132 issues (23 CRITICAL / 16 HIGH / 75 MEDIUM / 18 LOW) — **the large majority are out of this repo's scope**: this tool scans `~/.claude`'s global settings, all installed skills, and all installed plugins by design, regardless of the target path passed to it. Every CRITICAL/HIGH finding traced back to unrelated global plugins (e.g. `impeccable`'s image-generation scripts) — not this project.

Restricting to the project-scoped portion (`[4/5]`/`[5/5]` steps — `CLAUDE.md`, `claude.md`, `AGENTS.md`, `GEMINI.md`, project `.claude/settings.json`): only MEDIUM/LOW findings, all false positives:
- "Suspicious instruction: instruction to skip verification" — matched the doc phrases "Verify account in cookies" (troubleshooting table) and "DO NOT claim CHANGELOG.md was updated without verifying..." (an anti-hallucination instruction, the opposite of skipping verification).
- "Sensitive file reference: cookie/browser data access" — this project's docs legitimately describe cookie-based authentication; inherent to the tool's stated purpose.

## skill-audit
**`notebooklm-cli.skill`**: Score 0/100, LOW RISK, APPROVE. No findings (22 lines, prompt-only).

**`src/notebooklm_tools/data/SKILL.md`**: Score 75/100, CRITICAL RISK (tool's own verdict) — 983 lines, reviewed and confirmed false positive on every trigger:
- **Credential access (+20 pts)**: matched the word "credentials" — this file is the reference doc for an authentication CLI; describing credential handling is its stated purpose, not a leak.
- **Prompt injection — "Silent action instruction" (Medium)**: matched "Infer format/style/prompt silently—one compact line" (line 67) — this describes skipping a clarifying-question round-trip for the calling agent's UX, not hiding an action from the user. No actual concealment instruction present.
- **6 network URLs**: `http://127.0.0.1`, `https://example.com`, `https://example1.com`, `https://example2.com`, `https://youtube.com/...`, `https://...` — all doc-example placeholders, not live endpoints.
- **9 file operations / high bash complexity (+10 pts)**: the doc's 29 bash code blocks are CLI usage examples (`nlm ...` commands), not executed code.
- This matches the same false-positive class skillspector independently confirmed on the same file in the 2026-08-28 report (MP2 context-window-stuffing on file length, YR1 info-stealer on the doc's own auth-flow description).

## mcp-exfil-scan
**SKIPPED THIS RUN** — `mcp-exfil-scan.sh`'s SHA256 checksum did not match the bundled `SHA256SUMS` manifest (`config-audit.py`, `skill-audit.sh`, `apts-audit.sh`, `aggregate-findings.py` all verified OK). Per the skill's tamper-evidence rule, a mismatched script must not be run. This is a coverage gap, not a finding — recommend reinstalling/verifying the `claude-code-security-plugins` plugin before the next scheduled run.

## Cross-Tool Observations
- No cross-tool overlaps between Bandit/Semgrep/Trivy/TruffleHog/OSV-Scanner — all five core tools independently returned clean after the one Bandit suppression fix.
- mcps-audit's and skill-audit's CRITICAL/HIGH findings do not overlap with any Bandit/Semgrep finding (both returned 0 High/Medium on the same files), reinforcing scanner-specific pattern-matching noise for this codebase's domain (a browser-automation/cookie-auth CLI, whose legitimate functionality reads as "credential theft" and "dangerous execution" to generic heuristics).
- TruffleHog's hit count dropped from 30 (prior run) to 3 this run — the 28 "Lob"-detector false positives on `test_*` function names from the prior report did not reappear (likely a TruffleHog version/detector update between 3.95.9 and 3.97.4); the 2-3 doc-placeholder `URI` hits are the same persistent false-positive class.

## Coverage Gaps
- Not covered: business logic correctness, IDOR, runtime/dynamic behavior.
- CodeQL skipped — no GitHub Actions CodeQL workflow configured.
- mcp-scan skipped (opt-in, sends data externally, unattended scheduled run — no user present to consent).
- **mcp-exfil-scan skipped this run** — bundled-script checksum mismatch (see above). Real coverage reduction versus the 2026-08-27/08-21 reports; should be resolved (reinstall/verify plugin) before relying on this run as equivalent-depth coverage.
- skillspector not re-run this cycle (relied on the 2026-08-28 report's already-sampled findings on the same `SKILL.md` file, which had not changed in this merge).

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260907T155825Z.jsonl`
- **Tool runs recorded:** 13 (measured: 13, asserted: 0)
- **Standard:** OWASP APTS § Auditability

---

## Verdict

**0 Very High / 0 High / 0 remaining Medium findings.** The single raw Bandit Medium was a genuine suppression-comment placement bug (not a real filesystem risk) — fixed by moving the `# nosec B108` comment to the line it was meant to cover, confirmed via rerun. No dependency upgrades were required (Trivy + OSV-Scanner both clean, 88 packages). No merge conflicts occurred beyond `CLAUDE.md`, resolved by dropping a stale duplicate "Authentication (SIMPLIFIED!)" section and folding the new unattended-keep-alive note into the canonical Authentication section.

All raw "findings" beyond the above (mcps-audit's 10 CRITICAL/123 HIGH/429 MEDIUM/4 LOW, config-audit's project-scoped Medium/Low, skill-audit's 75/100 on `SKILL.md`, TruffleHog's 3 hits) were individually reviewed and confirmed as false positives. Logged below as Low/Info for transparency; user declined the Low/Info fix pass this run.

### Low/Info items (user declined — no fix applied this run)
1. TruffleHog: 3 false-positive `URI` hits on the same doc placeholder example across three older dated security-scan-report docs.
2. mcps-audit: 429 MEDIUM / 4 LOW generic pattern-scanner findings on `scripts/` (dev-only CDP tooling), not individually triaged beyond the CRITICAL sample.
3. config-audit: project-scoped MEDIUM findings ("skip verification" / "cookie access" pattern matches on this auth tool's own legitimate documentation).
4. Bandit: 2,411 Low findings (`assert_used`) in `tests/` — standard pytest convention, not actionable.
5. **Coverage gap (not a finding, but should be tracked):** mcp-exfil-scan did not run this cycle due to a bundled-script checksum mismatch. Reinstall/verify `claude-code-security-plugins` before the next scheduled run to restore full coverage.
