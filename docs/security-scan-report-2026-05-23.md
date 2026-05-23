# Security Scan Report — 2026-05-23 (post-merge v0.6.11)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD:** `6c73f3e` (merge of `origin/main` v0.6.11)
**Standard:** OWASP APTS-aligned

## Merged commits
- `31df628` fix: reconcile false-negative errors on `source_add` and `research_import` (closes #196, @mdshearer)
- `a8695f0` Merge branch 'fix/snap-chromium-profile'
- `5f42a23` refactor: clean up snap detection and add tests
- `222dd53` test(download): assert cross-site Sec-Fetch-Site and Referer headers
- `5d5b986` fix(download): set Sec-Fetch-Site: cross-site for cross-domain artifact downloads (#193, @responsiblefleet)
- `febfb0f` fix: use snap-accessible profile directory for snap-installed browsers (#195, @ildella)

## Merge resolution
- Conflict in `src/notebooklm_tools/utils/cdp.py` in `cleanup_chrome_profile_cache()`.
  - HEAD: single-directory cleanup loop with the local SEC-007 hardening — `except Exception as _e: _logger.debug(...)` instead of a bare `pass`.
  - origin/main: refactored into a `_clean_profile_dir()` helper that cleans both the standard profile dir and the snap-accessible profile dir (PR #195), but used a silent `except Exception: pass`.
  - Resolution: adopted origin's snap-aware `_clean_profile_dir()` structure AND kept local's stricter SEC-007 `_logger.debug(...)` logging inside the helper. No security semantics lost; snap coverage gained.

## Tools run

| Tool | Version | Result |
|------|---------|--------|
| Gitleaks | 8.30.1 | 540 commits / 9.34 MB scanned — **0 leaks** |
| Bandit | 1.9.4 | 23,024 LOC — 5 Low (see below), 0 Medium/High |
| Semgrep p/owasp-top-ten + p/python + p/secrets | latest | 95 files / 191 rules — **0 findings** |
| Trivy fs | 0.69.3 | `uv.lock` — 1 Medium (idna, fixed), 0 secrets, 0 misconfig |
| OSV-Scanner | 2.3.5 | 89 packages in `uv.lock` — 2 vulns (idna + starlette, both fixed) |
| TruffleHog | 3.94.2 | git, 7,321 chunks / 9.61 MB — **0 verified, 0 unverified** |

## Findings

### Very High / High
- None.

### Medium / Unknown (fixed)
1. **idna 3.11 → 3.16** — CVE-2026-45409 (CVSS 6.9, Medium), GHSA-65pc-fj4g-8rjx.
   Specially crafted inputs to `idna.encode()` could trigger excessive processing. Fixed via `uv lock --upgrade-package idna` (fix version 3.15; resolver picked 3.16).
2. **starlette 0.50.0 → 1.0.1** — PYSEC-2026-161 / GHSA-86qp-5c8j-p5mr (no published CVSS; auth-bypass class).
   Starlette reconstructs the request URL from the HTTP Host header without validating it, allowing authentication bypass on path-based auth. Reaches this project via the MCP HTTP transport (FastMCP 3.2.3). Fixed via `uv lock --upgrade-package starlette` (major bump 0.x → 1.0.1).
   - Post-fix verification: `uv sync` OK → OSV re-scan **"No issues found"** → full test suite **862 passed, 37 skipped** → MCP server import OK with starlette 1.0.1 + fastmcp 3.2.3.

### Low (accepted, not fixed — user declined this cycle)
1. **B110 — try_except_pass** (`core/research.py:400`) — in the newly merged `_reconcile_source` polling path; the `pass` is intentional so the original error is re-raised when polling can't confirm the source landed.
2. **B110 — try_except_pass** (`core/sources.py:104`) — documented in-code: "If listing itself fails, don't mask the original error."
3. **B607 — start_process_with_partial_path** (`utils/cdp.py:1038`) — `taskkill` is a Windows System32 built-in, not user-controlled.
4. **B603 — subprocess_without_shell_equals_true** (`utils/cdp.py:1038`) — `shell=False`, hardcoded args plus integer-coerced PID, no untrusted input.
5. **B110 — try_except_pass** (`utils/cdp.py:1041`) — best-effort process kill; suppression is intended semantics.

## Coverage gaps
- Not covered by automated scanning: business-logic flaws, IDOR, runtime authorization checks, MCP runtime exfiltration during live operation.
- `mcps-audit`, `mcp-scan`, `config-audit`, `skill-audit`, `mcp-exfil-scan` were not run this cycle (no MCP manifest changes in the merged commits).

## Overall risk posture
**Clean after fixes.** Two dependency vulnerabilities (idna Medium, starlette auth-bypass) introduced/carried in upstream v0.6.11 were upgraded and verified clean. Five Low-severity static-analysis findings (all practical false positives on controlled input) are documented and accepted; the user declined to annotate them this cycle.
