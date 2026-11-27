# Security Scan Report — 2026-11-27

**Target:** notebooklm-mcp-cli (post-merge origin/main, v0.16.9)  **Git HEAD:** 5fd34f7 with origin/main d639213 merged into the index
**Standard:** OWASP APTS-aligned
**Scope:** repository working tree. Bandit on `src`, `scripts`, `tests`; Semgrep on git-tracked files not excluded by `.semgrepignore`; global `~/.claude` rows from config-audit are listed but out of scope.

## Coverage
| Tool | Ran? | Version | Result / skip reason |
|---|---|---|---|
| Gitleaks | OK | 8.30.1 | 983 commits, no leaks |
| Bandit | OK | 1.9.4 | before fix: 0 High, 20 Medium, 4917 Low; after fix: 0 Medium, 4917 Low |
| Semgrep | OK | 1.180.0 (pipx) | owasp-top-ten (140 files), python (140), secrets (262): 0 findings. `.semgrepignore` skipped 199 files; 1 file over 300 KB skipped (`mcps-audit-report.pdf`) |
| Trivy | OK | 0.76.1 | `uv.lock`: 0 vulnerabilities (dev dependencies suppressed by default) |
| OSV-Scanner | OK | 2.7.0 | `uv.lock`: 98 packages, 0 vulnerabilities |
| TruffleHog | OK | 3.99.7 | git history: 0 verified, 8 unverified |
| config-audit | OK | bundled | see below |
| mcp-exfil-scan | OK | bundled | 0/100, CLEAN |
| skill-audit | OK | bundled | `.skill` 0/100; `data/SKILL.md` 75/100 |
| skillspector | OK | 2.13.0 `--no-llm` | `data/`: 23 issues, same set as the 11-26 baseline; inspection partial |
| mcps-audit | OK | 1.0.0 | `src`: 446 heuristic hits. Run through `npx` with a copy already in the local npx cache |
| CodeQL | N/A | - | no CodeQL workflow |
| mcp-scan, skillspector LLM mode, Jev triage of findings | SKIPPED | - | opt-in, no user to consent |

## Fixed
| Severity | Finding | Fix |
|---|---|---|
| Medium ×19 | Bandit B108 hardcoded `/tmp` path: `tests/cli/test_setup_wizard.py` (5), `tests/core/test_download.py` (12), `tests/services/test_downloads.py` (2) | False positive (path strings in mocks, no file created). `# nosec B108` with justification |
| Medium ×1 | Bandit B102 `exec`: `tests/test_launcher.py:33` | False positive (test stub emulating `python -c`). `# nosec B102` with justification |

Earlier reports scanned `src` only with Bandit, so these test-tree rows were not counted before. The comments can conflict with future upstream edits to the same lines.

## Dependencies, secrets and code SAST
No Very High or High findings from Gitleaks, Bandit, Semgrep, Trivy, OSV-Scanner or TruffleHog.

### Bandit Low (4917, left by design)
| ID | All | `src` only |
|---|---|---|
| B101 assert | 4476 | 3 |
| B106 hardcoded password argument | 283 | 1 |
| B105 hardcoded password string | 79 | 2 |
| B603 subprocess without shell | 30 | 14 |
| B404 subprocess import | 20 | 4 |
| B110 try/except/pass | 18 | 16 |
| B607 partial executable path | 10 | 4 |
| B112 try/except/continue | 1 | 1 |

`src` total: 45, unchanged from the last scan. The rest are in `tests` and `scripts`.

### TruffleHog (8 unverified, false positive)
All 8 are one placeholder example URL on the `bar.com` domain with dummy userinfo, quoted in older `docs/security-scan-report-*.md` files. Not a credential.

## mcps-audit (446 hits, all left unchanged)
Keyword-based rules. Critical and High snippets were reviewed by rule; the 341 Medium and 2 Low rows were not reviewed one by one.

| Severity | Rule | Count | Location | Disposition |
|---|---|---|---|---|
| Critical | AS-001 command execution | 1 | `cli/commands/doctor.py:450` | False positive: `subprocess.run` with `shutil.which` path, fixed args, no shell |
| Critical | AS-005 injection pattern | 2 | `core/download.py:1388,1416` | False positive: docstring and comment mentioning a `<script>` tag |
| High | AS-002 hardcoded secret | 3 | `core/credential_backend_worker.py` | False positive: an error class name containing "Credential" |
| High | AS-004 file input near prompts | 26 | `cli/utils.py`, `core/`, `utils/` | False positive: local file I/O, `Popen` and comments |
| High | AS-006 unsandboxed execution | 1 | `cli/commands/doctor.py:450` | Same line as AS-001 |
| High | AS-008 auto-approval | 36 | `cli/` | By design: opt-in `--confirm` flag, default off |
| High | AS-011 dynamic HTTP | 34 | `core/`, `mcp/`, `services/`, `utils/` | False positive: `urllib.parse` use and two fixed pypi.org requests |
| Medium | AS-003 permissions | 233 | `src` | Heuristic (words such as delete or manage) |
| Medium | AS-010 no logging | 108 | `src` | Heuristic, per file |
| Low | AS-007 dependency integrity | 2 | `src` | `uv.lock` at repo root pins dependencies |

Only two hits fall on lines added by this merge: AS-011 on `core/sources.py:23` (an `urlsplit` import) and AS-010 on the new `services/_research_import_guard.py`.

## skillspector (23 issues)
Paths are under `src/notebooklm_tools/data/`. The only change to these files in this merge is the version string.

| Severity | Rule | Location | Disposition |
|---|---|---|---|
| High | P2 hidden instructions | AGENTS_SECTION.md:1 | False positive: version/start/end HTML comment markers |
| High | RA1 self-modification | AGENTS_SECTION.md:95, SKILL.md:904, references/command_reference.md:1255 | By design: documents `nlm skill install/update` and aliases |
| High | AE1 incomplete inspection | SKILL.md:106, 109, 112, 1159 | Coverage gap: scanner parse limit |
| High | YR1 info_stealer | SKILL.md:156 | False positive: `save_auth_tokens` placeholder example |
| High | MP3 memory manipulation | SKILL.md:751, references/command_reference.md:968, references/workflows.md:190 | False positive: REPL `/clear` command list |
| High | P6 prompt extraction | references/studio-prompting-guide.md:67 | False positive: previews the Studio generation prompt |
| High | PE3 credential access | references/troubleshooting.md:191 | False positive: Keychain troubleshooting |
| High | AS1 agent config access | references/troubleshooting.md:274 | False positive: user-edited Codex network setting |
| Medium | EA2 autonomous decision | SKILL.md:68, 567; references/studio-prompting-guide.md:98, 184 | By design (upstream fast track; confirm gate stays) |
| Medium | RA2 session persistence | SKILL.md:878, 942; references/troubleshooting.md:150 | By design: setup, batch examples, login profile |
| Low | PE1 excessive permissions | references/troubleshooting.md:383 | False positive: Drive permission check |

## skill-audit
- `notebooklm-cli.skill`: 0/100 Low.
- `data/SKILL.md`: 75/100 (labelled Critical by the tool). Drivers: one "credentials" keyword, one Medium "silent action" match (line 206, "rather than silently returning empty tokens"), bash block complexity. False positives.

## config-audit
- Repo-scoped: 10 Medium rows (7 unique; `CLAUDE.md` is listed again as `claude.md` on a case-insensitive filesystem). `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` match credential and cookie wording in auth documentation; `CLAUDE.md` also matches "skip verification". False positives; these files did not change in this merge.
- Outside repo scope (user-global `~/.claude`): 15 Critical, 8 High, 54 Medium, 17 Low. Not changed. From `settings.json`: one High (a `PermissionRequest` hook using curl; its only URL is on 127.0.0.1) and 14 Medium (13 broad hook matchers, 1 "dangerous mode permission prompt is disabled").

## Verification
- `uv run pytest -q`: 2777 passed, 40 skipped (after merge and again after the fix).
- `ruff check`: passed. `ruff format --check`: one file, `mcp/tools/auth.py`, already differed from upstream before this merge and was left as is.
- Jev: test-only change adds no behavior change (verified, 0.89); research import claim is created before the call and blocks replay (verified, 0.92); incremental download does not overwrite a concurrently published file (verified, 0.98).
- Codex read-only review (`codex exec -s read-only`): 1 High, 4 Medium, 1 Low in upstream's new code, listed below. It found nothing further in cookie parsing, Firefox handling or source URL validation, and confirmed the test-only edits change no behavior.

## Codex review findings (open, not fixed)
These come from the validation review, not from the scanners. All are in code merged from upstream and were left unchanged for the owner to decide, to avoid new fork-only edits in upstream logic. "Code read" means the path was checked in the source; none were reproduced here.

| Severity | Location | Finding | Check | Suggested fix |
|---|---|---|---|---|
| High | `services/research.py:419` | The auto-import claim is made for task A, but `import_research()` polls again and the core poll can fall back to task B. B is then imported and A marked confirmed, so a later request for B can import it twice. Needs the provider's task list to change between the two polls | Code read: confirmed. Codex reports an in-memory reproduction | Reject a task ID mismatch on the guarded path before the import call, or pass the validated poll result through |
| Medium | `services/_research_import_guard.py:68` | In File mode on a case-insensitive filesystem, `default` and `DEFAULT` load the same credentials but hash to different claims | Code read: case collisions are checked only in strict (protected) mode | Hash a canonical profile identity |
| Medium | `services/_research_import_guard.py:66` | The parent directory is synced only when the claim directory is created; if that sync fails, later calls skip it. Matters only on power loss | Code read: confirmed | Sync the storage root before every import |
| Medium | `services/_research_import_guard.py:62` | Direct `mkdir()` bypasses `config.safe_mkdir`, the workaround for the Windows Python 3.14 `WinError 183` problem | Code read: direct call confirmed; not tested on Windows | Use `safe_mkdir` |
| Medium | `services/downloads.py:773` | With `skip_existing=True`, `os.link()` fails on filesystems without hard links (exFAT, FAT) and the finished download is discarded | Code read: only `FileExistsError` is handled | Fall back to exclusive-create and copy |
| Low | `services/downloads.py:784` | A viewer file renamed to `.pdf` can be downloaded again on the next incremental run when names differ only in case | Not checked | Reserve the actual filename before publishing |

Validator disagreement: Jev verified that a claim is created before the call and the same claim is not replayed. The Codex High finding is a gap that claim does not cover (the call can act on a different task).

## Audit log
- `/tmp/css-scan-20261127T122940Z.jsonl`, 16 tool runs recorded (all measured).
