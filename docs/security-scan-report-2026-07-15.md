# Automated Security Scan Report

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-15T02:20:45Z
**Git HEAD:** 37cfa63 (post-merge of origin/main v0.8.6–v0.8.7)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    37cfa63
Include:     all supported (project source; .venv excluded)
Exclude:     .venv/, tests/ (bandit scoped run only), .gitignore honored
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 655 commits, ~10.28 MB | — |
| Bandit | OK | 1.9.4 | src/ + desktop-extension/ (pyproject `[tool.bandit]` scope) | `tests/`, `.venv/` excluded by repo convention |
| Semgrep (owasp-top-ten) | OK | 1.168.0 | 106 files, 153 rules | — |
| Semgrep (python) | OK | 1.168.0 | 106 files, 151 rules | — |
| Semgrep (secrets) | OK | 1.168.0 | 168 files, 38 rules | 1 file >300 KB skipped (`mcps-audit-report.pdf`, binary) |
| Trivy | OK | 0.71.2 (not in compromised list) | uv.lock (88 packages) | — |
| TruffleHog | OK | 3.95.6 | 8,461 chunks, 10.6 MB | — |
| OSV-Scanner | OK | 2.4.0 | uv.lock (88 packages) | — |
| mcps-audit | OK | 1.0.0 | 185 files, ~50k lines | — |
| CodeQL | SKIPPED | — | — | No `.github/workflows/codeql.yml` in this fork |
| mcp-scan | OPT-IN | — | — | Not run (sends data to invariantlabs.ai; not requested) |
| skill-audit | OK | bundled | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| config-audit | OK | bundled | Global `~/.claude` + project | Scans global config by design — most findings out of this repo's scope |
| mcp-exfil-scan | SKIPPED | bundled | — | Bundled script `mcp-exfil-scan.sh` failed SHA256SUMS integrity check — not run per operational rule (do not run on checksum mismatch) |
| skillspector | SKIPPED | — | — | No new AI-skill artifacts introduced in this merge |

## Gitleaks — Secrets in git history
**Summary:** 0 leaks. 655 commits scanned, ~10.28 MB, 870ms.

## Bandit — Python SAST
**Summary (scoped via `pyproject.toml` `[tool.bandit]`):** 1 new Low finding (before fix), 0 Medium/High.
- `src/notebooklm_tools/utils/cdp.py:1018` — `except Exception: pass` in `execute_cdp_command` retry fallback, missing `# nosec` justification comment (the file's other 5 broad excepts already carry one). **Fixed** — added `# nosec B110` with reason (stale cached connection retry).

An earlier unscoped run against the whole tree (including `tests/` and `.venv/`) reported inflated counts (Low 1784, Medium 74) — all `B101 assert_used` in `tests/` (expected pytest pattern, excluded by repo convention) and `B108 hardcoded_tmp_directory` in test mocks (`/tmp/...` literals in test fixtures, not runtime paths).

## Semgrep — Multi-lang SAST
**Summary:** 0 findings across all three rulesets.
- `p/owasp-top-ten`: 0 findings, 106 files, 153 rules
- `p/python`: 0 findings, 106 files, 151 rules
- `p/secrets`: 0 findings, 168 files, 38 rules

## Trivy — Deps / IaC / secrets
**Summary:** `uv.lock` — 0 vulnerabilities. Trivy 0.71.2, not affected by the GHSA-69fq-xp46-6x23 supply-chain compromise (only 0.69.4–0.69.6 affected).

## TruffleHog — Secrets with live verification
**Summary:** 0 verified, 0 unverified secrets. 8,461 chunks / 10.6 MB scanned in 1.05s.

## OSV-Scanner — SCA
**Before fix:** 1 High vulnerability — `click 8.3.2` (PYSEC-2026-2132, CVSS 7.2), fix available in 8.3.3+.
**After fix:** 0 issues found (upgraded to `click 8.4.2`).

## mcps-audit — MCP OWASP Top 10 heuristic scan
**Verdict:** FAIL, risk score 100/100, 520 findings (10 CRITICAL, 111 HIGH, 396 MEDIUM, 3 LOW) across 185 files / 49,986 lines.

Investigated the CRITICAL "Dangerous execution" findings — all in `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py`, one-off local developer debug utilities not part of the installed package (`pyproject.toml` only exposes `nlm`/`notebooklm-mcp` as `[project.scripts]`; these files aren't referenced by any packaged module or MCP tool). They call CDP `Runtime.evaluate` against the developer's own local Chrome profile for DOM inspection during development — no remote/untrusted input path, no MCP tool exposure. **Confirmed false positive**, consistent with the 2026-07-07 scan's identical finding on the same files.

The bulk of MEDIUM/HIGH findings (AS-010 "no logging/auditing" on scripts, AS-003 "high-risk permission pattern" matching string literals like `RPC_LABEL_DELETE` in dev/test scripts) are heuristic string matches on constant names and comments, not exploitable code paths. This tool has a known high false-positive rate for this project (documented in prior scan reports) and no allow-list mechanism for dev-only scripts.

## skill-audit — Skill security scan
- `notebooklm-cli.skill`: risk score 0/100, LOW RISK, APPROVE. No dangerous patterns, no prompt injection, no credential access.
- `src/notebooklm_tools/data/SKILL.md`: risk score 75/100, flagged CRITICAL by the heuristic. Investigated both flags:
  - **"Credential access" (+20)** — the file documents `nlm login` for the CLI's own auth flow; this is a legitimate auth tool's user-facing skill doc, not credential exfiltration.
  - **"Silent action instruction" (Medium)** — matched the phrase "Infer format/style/prompt silently" in the Studio fast-track guidance, meaning "don't ask clarifying questions before drafting a suggestion," not "hide the action from the user." The same guidance explicitly requires `studio_create(confirm=True)` — the user-facing confirmation gate is preserved.
  - **Confirmed false positive.** This is the project's own AI-facing product documentation (ships as `src/notebooklm_tools/data/SKILL.md`, referenced in `CLAUDE.md`'s version-alignment list) describing the tool's own credential and confirm-gated Studio flows — heuristic pattern-matching on expected domain vocabulary ("credentials", "silently infer"), not an injected instruction.

## config-audit — Claude config audit
Scanned the full `~/.claude` global configuration (skills, plugins, hooks) plus this project — by design this tool audits the *environment*, not just the scan target, so the great majority of its 73 findings (8 CRITICAL, 11 HIGH, 45 MEDIUM, 9 LOW) belong to unrelated global skills/plugins (`anysearch`, `caveman`, `optimize`, `qa`, official plugin examples, etc.) and are out of this repo's scope.

Only 4 findings touch this project (`CLAUDE.md` / case-duplicate `claude.md` on the same case-insensitive filesystem path):
- 2× MEDIUM "sensitive file reference: credentials/cookie file access" — matched the Authentication and Troubleshooting sections, which document the project's own (legitimate) cookie-based auth mechanism.
- 2× MEDIUM "suspicious instruction: instruction to skip verification" — matched "Verify account in cookies" (a troubleshooting row telling the user *to* verify) and "DO NOT claim CHANGELOG.md was updated without verifying" (an instruction *requiring* verification). Both are the opposite of what the pattern name suggests.

**Confirmed false positives**, all on the project's own documentation.

## mcp-exfil-scan — Not run
The bundled `mcp-exfil-scan.sh` script failed its `SHA256SUMS` integrity check during pre-flight (installed checksum `6f0219b...` vs. computed `3ca4126...`). Per the skill's operational rule, a mismatched bundled script must not be run. This affects the *scanner tool itself* (plugin cache), not the target repository — no conclusion about the target's MCP exfiltration surface can be drawn from this gap. Flagging for the user to reinstall/verify the `claude-code-security-plugins` plugin.

## Cross-Tool Observations
- Gitleaks, TruffleHog, and Semgrep's secrets ruleset independently agree: 0 secrets in source or git history.
- Bandit (scoped) and Semgrep (owasp/python) independently agree: 0 real Medium/High/Critical code-level findings in project source, after the one Low nosec fix.
- mcps-audit, config-audit, and skill-audit all produce large raw counts but every investigated CRITICAL/HIGH finding traced back to either (a) out-of-scope global config, (b) dev-only debug scripts with no packaged/MCP exposure, or (c) heuristic string-matching on the project's own legitimate auth/credential documentation. No cross-tool corroboration of a real vulnerability beyond the OSV-Scanner `click` finding.

## Coverage Gaps
- `mcp-exfil-scan` not run (bundled-script checksum mismatch — tooling issue, not a target-repo finding).
- CodeQL skipped (no workflow configured in this fork).
- `mcp-scan` and skillspector LLM-mode not run (opt-in, not requested this run; skillspector skipped as no new AI-skill artifacts were introduced).
- Business logic, IDOR, and runtime behavior are outside static-scan coverage.

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 (real) | mcps-audit's 10 CRITICAL and config-audit's 8 CRITICAL are all false positives (dev scripts, out-of-scope global config) |
| High | 1 | `click` 8.3.2 → 8.4.2 (PYSEC-2026-2132) — **Fixed** |
| Medium | 0 (real) | mcps-audit's 396 MEDIUM and config-audit's 45 MEDIUM are heuristic false positives on dev/test scripts and legitimate doc text |
| Low | 1 | Bandit B110 in `cdp.py:1018` — **Fixed** (added `# nosec` justification) |
| Info | skill-audit 75/100 on `data/SKILL.md`, config-audit project-scoped flags | All confirmed false positives — see analysis above |

## Fixes Applied
- `uv lock --upgrade-package click` → `uv sync`: click 8.3.2 → 8.4.2, resolving PYSEC-2026-2132 (CVSS 7.2). Verified with a clean re-run of OSV-Scanner.
- `src/notebooklm_tools/utils/cdp.py:1018` — added `# nosec B110` with reason to the one broad `except Exception: pass` missing the repo's established justification-comment convention.
- Verified after fixes: `uv run pytest -q` → 1120 passed, 39 skipped, 0 failed. `ruff check .` and `ruff format --check .` pass.

## Tools Used
Gitleaks 8.30.1 · Bandit 1.9.4 · Semgrep 1.168.0 · Trivy 0.71.2 · TruffleHog 3.95.6 · OSV-Scanner 2.4.0 · mcps-audit 1.0.0 · config-audit (bundled) · skill-audit (bundled)

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260715T022045Z.jsonl`
- **Tool runs recorded:** 13 (measured: 13, asserted: 0)
- **Standard:** OWASP APTS § Auditability
