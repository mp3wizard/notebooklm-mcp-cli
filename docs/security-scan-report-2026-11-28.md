# Security Scan Report — 2026-11-28

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.10)  **Git HEAD:** fbc8518 (merge of origin/main ef3bb8e)
**Standard:** OWASP APTS-aligned
**Scope:** repository working tree. Bandit on `src`, `scripts`, `tests`, `desktop-extension`; Semgrep on git-tracked files not excluded by `.semgrepignore`; global `~/.claude` rows from config-audit are listed but out of scope.

## Result
No code, dependency or secret finding at Medium or above from Bandit, Semgrep, Trivy, OSV-Scanner, Gitleaks or TruffleHog. The heuristic skill and MCP scanners report the same counts as on 2026-11-27 (triaged below). The scanner results needed no fixes and no code or dependency changed. Separately, the Codex validation review reports 1 High and 3 Medium findings that are open and not fixed (see below).

## Coverage
| Tool | Ran? | Version | Result / skip reason |
|---|---|---|---|
| Gitleaks | OK | 8.30.1 | 987 commits, no leaks |
| Bandit | OK | 1.9.4 | 0 High, 0 Medium, 4922 Low; 189 potential issues skipped by `# nosec` |
| Semgrep | OK | 1.180.0 (pipx) | owasp-top-ten (140 files), python (140), secrets (263): 0 findings. Files over 300 KB and `.semgrepignore` entries are skipped |
| Trivy | OK | 0.76.1 | `uv.lock`: 0 vulnerabilities (dev dependencies suppressed by default) |
| OSV-Scanner | OK | 2.7.0 | `uv.lock`: 98 packages, 0 vulnerabilities |
| TruffleHog | OK | 3.99.7 | git history: 0 verified, 8 unverified |
| config-audit | OK | bundled | see below |
| mcp-exfil-scan | OK | bundled | 0/100, CLEAN |
| skill-audit | OK | bundled | `.skill` 0/100; `data/SKILL.md` 75/100 |
| skillspector | OK | 2.13.0 `--no-llm` | `data/`: 23 issues; inspection partial |
| mcps-audit | OK | 1.0.0 | `src`: 446 heuristic hits. Run with `npx --offline` from the local cache. It overwrote the tracked `mcps-audit-report.pdf`, which was restored |
| CodeQL | N/A | - | no CodeQL workflow |
| mcp-scan, skillspector LLM mode, Jev triage of findings | SKIPPED | - | opt-in, no user to consent |

## Findings by severity (scanners)
| Severity | Code / dependency / secret tools | Heuristic skill and MCP tools (repo scope) |
|---|---|---|
| Very High / Critical | 0 | mcps-audit 3; `data/SKILL.md` skill-audit rating |
| High | 0 | mcps-audit 100; skillspector 14 |
| Medium | 0 | mcps-audit 341; skillspector 8; config-audit 10 rows |
| Low / Info | Bandit 4922; TruffleHog 8 unverified | mcps-audit 2; skillspector 1 |

### Bandit Low (4922, left by design)
`src` total: 45, unchanged from the last scan (B101 3, B105 2, B106 1, B110 16, B112 1, B404 4, B603 14, B607 4). The rest are in `tests`, `scripts` and `desktop-extension`; the +5 since 11-27 come from upstream's new tests (B101 +4, B106 +1).

### TruffleHog (8 unverified, false positive)
All 8 are URI-detector hits in older `docs/security-scan-report-*.md` files: the placeholder example URL noted in earlier reports. Not a credential.

## mcps-audit (446 hits, left unchanged)
Severity counts (Critical 3, High 100, Medium 341, Low 2) are identical to the [2026-11-27 report](security-scan-report-2026-11-27.md), which lists the rule-by-rule triage of the Critical and High rows as false positive or by design. This run's rows were not re-reviewed one by one.

## skillspector (23 issues)
Same rules and locations as the [2026-11-27 report](security-scan-report-2026-11-27.md) (false positive, by design, or scanner parse limit). The only change to `src/notebooklm_tools/data/` in this merge is the version string.

## skill-audit
`data/SKILL.md` 75/100 (labelled Critical by the tool), same drivers as before: a "credentials" keyword, one Medium "silent action" match and bash block complexity. False positives.

## config-audit
- Repo-scoped: 10 Medium rows on `CLAUDE.md` (also listed as `claude.md` on a case-insensitive filesystem), `AGENTS.md` and `GEMINI.md`. Auth documentation wording. These files did not change in this merge.
- Outside repo scope (user-global `~/.claude`): 15 Critical, 8 High, 54 Medium, 17 Low. Not changed.

## Verification
- `uv run pytest -q`: 2784 passed, 40 skipped.
- `ruff check`: passed. `ruff format --check`: one file, `mcp/tools/auth.py`, already differed from upstream before this merge and was left as is.
- Jev: each viewer request and redirect is checked before sending (verified, 0.98); HTTP 401 or a sign-in page raises `AuthenticationError` (verified, 1.00).
- CI's new step, run locally with Typer 0.29.3 (`test_login_storage_choice.py`, `test_mcp_cli_parity.py`): 36 passed.
- Codex read-only review (`codex exec -s read-only`) of `git diff f87c4f5 HEAD`: 1 High, 3 Medium, listed below. It found the viewer guard blocks the initial URL and each redirect before sending in the cases it checked, callers do not swallow `AuthenticationError`, and nothing actionable in the parity walk or CI change.

## Codex review findings (open, not fixed)
These come from the validation review, not from the scanners. They were left unchanged for the owner to decide, to avoid new fork-only edits in upstream download logic that cannot be checked against real Google hosts in an unattended run.

| Severity | Location | Finding | Check | Suggested fix |
|---|---|---|---|---|
| High | `core/download.py:215`, `:318`; `core/base.py` `_get_httpx_cookies` | The final file transfer (sync and async) follows redirects with no per-hop check, and rebuilt cookies lose the `Secure` attribute. A redirect to `http://*.googleusercontent.com` sends the session cookie in cleartext; a redirect to an off-domain host is followed (no Google cookie sent) and its content is saved. Needs a trusted Google host to issue such a redirect. Existed before this merge | Reproduced by Codex and again in this run with a mock transport and a synthetic cookie | Check HTTPS and the host allowlist on each hop of the final transfer; keep `Secure` on cookies |
| Medium | `core/download.py:1244` | New in this merge: any viewer HTML containing an `accounts.google.com/ServiceLogin` link, such as an HTTP 503 page with a footer link, is reported as expired auth | Reproduced by Codex; not rerun here | Require stronger evidence of a login page (title or form) |
| Medium | `core/download.py:1244` | New in this merge: a `<title>Sign in - Google Accounts</title>` page (HTTP 200 or 403) is not detected, so no login guidance is shown | Reproduced by Codex; not rerun here | Add that title variant with regression tests |
| Medium | `tests/core/test_download.py:1123` | The new tests do not cover an untrusted intermediate hop or HTTPS to HTTP; they still pass with the allowlist branch removed | Reproduced by Codex in memory; not rerun here | Add those cases and assert the forbidden destination never reaches the transport |

Validator disagreement: Jev verified the per-redirect check, which holds for the viewer request only. Codex agrees the viewer guard works, but the final download is unguarded and the new tests do not prove the allowlist.

## Open from earlier review (not fixed)
The six Codex findings from 2026-11-27 (1 High, 4 Medium, 1 Low in `services/research.py`, `services/_research_import_guard.py` and `services/downloads.py`) are still open: this merge does not change those files. Details are in the [2026-11-27 report](security-scan-report-2026-11-27.md).

## Audit log
`/tmp/css-scan-20261128T023920Z.jsonl`, 15 records including the header.
