# Security Scan Report — 2026-05-18 (post-merge v0.6.10)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD:** `caff319` (merge of `origin/main` v0.6.10)
**Standard:** OWASP APTS-aligned

## Merged commits
- `1a80900` fix: improve Windows CDP authentication reliability (PR #192, @jonathanzhan1975)
- `a390b90` chore: bump version to 0.6.10
- `446f99c` docs: credit @jonathanzhan1975 for Windows CDP fix (#192)

## Merge resolution
- Conflict in `src/notebooklm_tools/utils/cdp.py` around `subprocess.Popen` call.
  - HEAD: kept explicit `stdout/stderr=PIPE` kwargs and `# nosec B603` justification.
  - origin/main: refactored to `subprocess.Popen(args, **kwargs)` so Windows `creationflags=CREATE_NEW_PROCESS_GROUP` (set above) applies.
  - Resolution: adopted origin's `**kwargs` form and re-attached the `# nosec B603` comment inline. No security semantics lost.

## Tools run

| Tool | Version | Result |
|------|---------|--------|
| Gitleaks | 8.30.1 | 534 commits / 9.31 MB scanned — **0 leaks** |
| Bandit | 1.9.4 | 22,805 LOC — 3 Low (see below) |
| Semgrep p/owasp-top-ten | latest | 101 files / 153 rules — **0 findings** |
| Semgrep p/python | latest | 101 files / 151 rules — **0 findings** |
| Semgrep p/secrets | latest | 146 files / 38 rules — **0 findings** |
| Trivy fs | 0.69.3 | `uv.lock` — **0 vulnerabilities**, 0 secrets |
| OSV-Scanner | 2.3.5 | 89 packages in `uv.lock` — **0 issues** |
| TruffleHog | 3.94.2 | git, 7,268 chunks / 9.57 MB — **0 verified, 0 unverified** |

## Findings

### Very High / High / Medium
- None.

### Low (accepted, not fixed)
All three findings are in the newly-merged `_kill_process()` helper added by PR #192 — `src/notebooklm_tools/utils/cdp.py:940-951`.

1. **B607 — start_process_with_partial_path** (`cdp.py:947`)
   `subprocess.run(["taskkill", "/F", "/PID", str(pid)], ...)`
   *Rationale to keep:* `taskkill` is a Windows built-in resident in `%SystemRoot%\System32`. There is no user-controlled input on the executable name; Windows resolves it from the protected system path.

2. **B603 — subprocess_without_shell_equals_true** (`cdp.py:947`)
   Same line as B607.
   *Rationale to keep:* `shell=False` (the default) is the safe form. All arguments are hardcoded literals plus an integer-coerced PID. No untrusted input is interpolated.

3. **B110 — try_except_pass** (`cdp.py:950-951`)
   *Rationale to keep:* The function's docstring explicitly states "Best effort to kill a process by PID." Suppressing the exception is the intended semantics — we do not want a stale-process cleanup pass to break the parent flow.

## Coverage gaps
- Not covered by automated scanning: business-logic flaws, IDOR, runtime authorization checks, MCP runtime exfiltration during live operation.
- `mcps-audit`, `mcp-scan`, `config-audit`, `skill-audit`, `mcp-exfil-scan` were not run this cycle (no MCP manifest changes in the merged commits).

## Overall risk posture
**Clean.** No high/medium issues introduced by upstream v0.6.10. Three Low-severity static-analysis findings on the new Windows zombie-cleanup helper are documented and accepted as false positives.
