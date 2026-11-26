# Security Scan Report — 2026-11-26

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.8)  **Git HEAD:** 2d37892 (merge commit, pre-fix)
**Standard:** OWASP APTS-aligned
**Scope:** repository working tree. Semgrep OWASP/Python on `src` + `tests`; Semgrep secrets on the whole repo.

## Coverage
| Tool | Ran? | Version | Result / skip reason |
|---|---|---|---|
| Gitleaks | OK | 8.30.1 | 973 commits, no leaks |
| Bandit | OK | 1.9.4 | `src`: 45 Low, 0 Medium, 0 High |
| Semgrep | OK | pipx | owasp-top-ten (141 files), python (133), secrets (260): 0 findings. `.semgrepignore` skipped 194 files; 1 file over 300 KB skipped (`mcps-audit-report.pdf`) |
| Trivy | OK | 0.76.1 | `uv.lock`: 0 vulnerabilities (dev dependencies suppressed by default) |
| OSV-Scanner | OK | 2.7.0 | `uv.lock`: 98 packages, 0 vulnerabilities |
| TruffleHog | OK | 3.99.7 | git history: 0 verified, 8 unverified |
| config-audit | OK | bundled | see below |
| mcp-exfil-scan | OK | bundled | 0/100, CLEAN |
| skill-audit | OK | bundled | `.skill` 0/100; `data/SKILL.md` 75/100 |
| skillspector | OK | 2.13.0 `--no-llm` | `data/`: 24 issues before fix, 23 after; inspection partial (75%) |
| CodeQL | N/A | - | no CodeQL workflow, CLI not installed |
| mcps-audit | SKIPPED | - | `npx` would fetch and run a remote package in an unattended run |
| mcp-scan, skillspector LLM mode, Jev triage | SKIPPED | - | opt-in, no user to consent |

## Fixed
| Severity | Finding | Fix |
|---|---|---|
| High | skillspector EA5, `references/troubleshooting.md:284`: shipped skill text suggested running Codex with `--sandbox danger-full-access` | Removed that alternative; the narrower `network_access = true` option stays. Rescan confirms the finding is gone |

## Dependencies and code SAST
No Very High, High or Medium findings from Gitleaks, Bandit, Semgrep, Trivy, OSV-Scanner or TruffleHog.

### Bandit Low (45, left by design)
| ID | Count | Files |
|---|---|---|
| B110 try/except/pass | 16 | setup_wizard.py (8), credential_store.py (3), setup.py, auth_migration.py, mcp/tools/_utils.py, auth_storage.py, config.py |
| B603 subprocess without shell | 14 | setup.py (5), setup_wizard.py (3), cdp.py (2), skill_package.py, credential_backend_worker.py, firefox.py, wsl.py |
| B404 subprocess import | 4 | setup_wizard.py, skill_package.py, credential_backend_worker.py, firefox.py |
| B607 partial executable path | 4 | setup.py (2), cdp.py, wsl.py |
| B101 assert | 3 | setup.py (2), auth_recovery_budget.py |
| B105 hardcoded password string | 2 | core/base.py, utils/firefox.py |
| B106 hardcoded password argument | 1 | mcp/tools/_utils.py |
| B112 try/except/continue | 1 | auth_storage.py |

### TruffleHog (8 unverified, false positive)
All 8 are one placeholder example URL on the `bar.com` domain with dummy userinfo, quoted in eight older `docs/security-scan-report-*.md` files (08-15, 08-27, 08-28, 09-07, 09-09, 09-14, 09-18, 09-23). Not a credential.

## skillspector (all 24 pre-fix issues)
Paths are under `src/notebooklm_tools/data/`. Line numbers are pre-fix.

| Severity | Rule | Location | Disposition |
|---|---|---|---|
| High | P2 hidden instructions | AGENTS_SECTION.md:1-102 | False positive: only HTML comments are the start/version/end markers; no invisible or bidi characters found |
| High | RA1 self-modification | AGENTS_SECTION.md:95 | By design: documents `nlm skill install/update` |
| High | RA1 self-modification | SKILL.md:904 | By design: documents skill command aliases |
| High | RA1 self-modification | references/command_reference.md:1255 | By design: same command aliases |
| High | AE1 incomplete inspection | SKILL.md:106 | Coverage gap: scanner parse limit on `references/workflows.md` |
| High | AE1 incomplete inspection | SKILL.md:109 | Same coverage gap |
| High | AE1 incomplete inspection | SKILL.md:112 | Same coverage gap |
| High | AE1 incomplete inspection | SKILL.md:1159 | Same coverage gap |
| High | YR1 info_stealer | SKILL.md:156 | False positive: `save_auth_tokens` example with a placeholder |
| High | MP3 memory manipulation | SKILL.md:751 | False positive: REPL `/clear` command list |
| High | MP3 memory manipulation | references/command_reference.md:968 | False positive: REPL `/clear` command list |
| High | MP3 memory manipulation | references/workflows.md:190 | False positive: REPL `/clear` command list |
| High | P6 prompt extraction | references/studio-prompting-guide.md:67 | False positive: "show prompt" previews the Studio generation prompt |
| High | PE3 credential access | references/troubleshooting.md:191 | False positive: Keychain prompt troubleshooting |
| High | AS1 agent config access | references/troubleshooting.md:274 | False positive: user-edited Codex network setting (the narrow option) |
| High | EA5 external model selection | references/troubleshooting.md:284 | **Fixed** (see above) |
| Medium | EA2 autonomous decision | SKILL.md:68 | By design (upstream): fast track still calls `studio_create(confirm=True)` |
| Medium | EA2 autonomous decision | SKILL.md:567 | By design: same fast-track flow |
| Medium | EA2 autonomous decision | references/studio-prompting-guide.md:98 | By design: silent inference of style/prompt from context |
| Medium | EA2 autonomous decision | references/studio-prompting-guide.md:184 | By design: picks `source_ids` without asking |
| Medium | RA2 session persistence | SKILL.md:878 | By design: documents the setup command writing MCP config |
| Medium | RA2 session persistence | SKILL.md:942 | False positive: batch command examples |
| Medium | RA2 session persistence | references/troubleshooting.md:150 | By design: creating a login profile |
| Low | PE1 excessive permissions | references/troubleshooting.md:389 | False positive: Drive document permission check |

## skill-audit
- `notebooklm-cli.skill`: 0/100 Low.
- `data/SKILL.md`: 75/100 (labelled Critical by the tool). Drivers: one "credentials" keyword match, one Medium "silent action" match (line 206, "rather than silently returning empty tokens"), and bash block complexity. All false positives.

## config-audit
- Repo-scoped: 10 Medium rows (7 unique; `CLAUDE.md` is listed twice as `claude.md` on a case-insensitive filesystem). `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` match "credentials file access" and "cookie/browser data access" in auth documentation; `CLAUDE.md` also matches "skip verification" on a line that requires verification. False positives; files unchanged since the last scan.
- Outside repo scope (user-global `~/.claude` hooks, skills and plugins): 15 Critical, 8 High, 57 Medium, 18 Low. Not reviewed or changed here.

## Verification
- `uv run pytest -q`: 2698 passed, 40 skipped (after merge and again after the fix).
- Codex read-only review of the 0.16.8 `src`/`tests` diff plus the fix: no findings.
- Jev: "sync download raises before replacing the output file on a login page" verified (0.88); "doc change only removes the `danger-full-access` advice" verified (0.97).

## Audit log
- `/tmp/css-scan-20261126T024200Z.jsonl`, 15 tool runs recorded (all measured).
