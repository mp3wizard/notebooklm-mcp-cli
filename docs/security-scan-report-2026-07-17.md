# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-17T04:10:57Z (local: 2026-07-17 11:10 +07)
**Git HEAD:** post-merge of `origin/main` (4 new commits: 563ca15, ed14a84, 9bab913, 8fc4d13 — v0.8.8)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    main (merged origin/main)
Include:     all supported (Python/JS/config), .venv excluded
Exclude:     .venv, .git-ignored paths
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|-----------------|
| Gitleaks | OK | 8.30.1 | 665 commits, ~10.3MB | — |
| Bandit | OK | 1.9.4 | 39,116 LOC (src/tests, `.venv` excluded) | — |
| Semgrep (OWASP) | OK | current | 106 Python files, 153 rules | 67 non-Python skipped by `--include` |
| Semgrep (Python) | OK | current | 106 Python files, 151 rules | same |
| Semgrep (secrets) | OK | current | 170 files, 38 rules | 1 file >0.3MB skipped |
| Trivy | OK | 0.71.2 | `uv.lock`, 88 packages | — |
| TruffleHog | OK | 3.95.6 | full git history, 8,545 chunks / 10.6MB | — |
| OSV-Scanner | OK | 2.4.0 | `uv.lock`, 88 packages | — |
| mcps-audit | OK | 1.0.0 | 185 files / 50,648 lines | — |
| config-audit | OK | bundled | `~/.claude` config + repo `.claude`/CLAUDE.md | — |
| skill-audit | OK | bundled | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | OK | bundled | 5 MCP configs, 10 skill files | — |
| CodeQL | SKIPPED | — | — | no CodeQL workflow in `.github/workflows/` |
| mcp-scan / skillspector LLM mode | SKIPPED | — | — | opt-in, not requested this run |

## Bandit — Python SAST
**Summary:** 0 High, 75 Medium, 1819 Low (production code only; `.venv` excluded)
All 75 Medium findings are confined to `tests/`: `B108 hardcoded_tmp_directory` from `/tmp/...` mock paths in `test_login.py`, `test_download.py`, `test_downloads.py`; and one `B102 exec_used` in `tests/services/test_auth_service.py:153` used to import a module under test. No production-code exposure.

## Semgrep — OWASP Top Ten / Python / Secrets
**Summary:** 0 findings across all three configs (342 rules total run against 106–170 files).

## Trivy — Dependency scan
**Summary:** 3 HIGH vulnerabilities found and **fixed this run**.
```
mcp 1.27.0 → CVE-2026-52869, CVE-2026-52870 (fixed 1.27.2), CVE-2026-59950 (fixed 1.28.1)
```
- CVE-2026-52869: HTTP transport served session requests without verifying the authenticated session.
- CVE-2026-52870: experimental task handlers allowed any client to access/modify another client's tasks.
- CVE-2026-59950: WebSocket server transport lacked Host/Origin validation.

**Fix applied:** `uv lock --upgrade-package mcp` → `mcp 1.28.1`, then `uv sync`. Re-scan confirms 0 vulnerabilities. Full test suite (`uv run pytest -m "not e2e"`) passes: 1150 passed, 38 skipped.

Trivy 0.71.2 is not in the compromised range (0.69.4–0.69.6, GHSA-69fq-xp46-6x23).

## TruffleHog — Verified secrets
**Summary:** 0 verified, 0 unverified secrets across 8,545 chunks / 10.6MB (full git history)

## OSV-Scanner — SCA via OSV.dev
**Summary:** Same 3 `mcp` HIGH vulnerabilities as Trivy (cross-tool confirmation) — resolved by the same fix. Post-fix re-scan: 0 issues, 88 packages.

## mcps-audit — MCP permission/agentic-AI audit
**Summary:** Verdict FAIL, Risk Score 100/100, 524 findings (10 Critical, 113 High, 398 Medium, 3 Low)

Same known high-false-positive pattern documented in prior scans of this repo: Critical/High findings are near-entirely pattern matches on legitimate CDP (Chrome DevTools Protocol) automation that is this project's core feature.
- `AS-001 "Dangerous execution"` on `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py` — JS executed **inside a user-controlled local Chrome session via CDP** to extract auth cookies for `nlm login`; documented, intentional purpose (CLAUDE.md Authentication section). Not remote/untrusted code execution.
- `AS-003 "High-risk permission pattern"` on `scripts/test_label_rpcs.py` — flags the string `RPC_LABEL_DELETE` in a **test script name/docstring**, not an unconfirmed production deletion path (the real `label` MCP tool routes through `services/sharing.py` validation).
- `AS-010 "No logging/auditing"` — informational; hits one-off dev/debug scripts, not the MCP server runtime (which has request-level error handling in `core/base.py`).

No fix applied — false positives against documented, intentional CDP-based auth extraction.

## config-audit — Claude Code config audit
**Summary:** Findings limited to Low/Medium, mostly outside this repo's control:
- 🟡 MEDIUM ×4: `CLAUDE.md`/`claude.md` matched on phrases like "Verify account in cookies" and "credentials file access" — these are **documentation** of the tool's own intentional cookie-based auth model, not an actual credential leak or an instruction to skip verification.
- 🔵 LOW ×9: hooks configuration present in various installed Claude Code plugins (`pordee`, `claude-video`, `openai-codex` ×2, `engram`, `addy-agent-skills`, `claude-plugins-official`, `caveman` ×2) — informational, user's globally-installed plugins, not part of this repository.

No repo-specific config issues.

## skill-audit — Skill file review
**Summary:**
- `notebooklm-cli.skill`: Risk 0/100 — LOW RISK / APPROVE.
- `src/notebooklm_tools/data/SKILL.md`: Risk 75/100 — flagged CRITICAL, but false positive: the "Silent action instruction" hit is the phrase "Silently infer" (line 66/401), which describes the AI agent skipping clarifying *questions* before `studio_create(confirm=True)` — the confirm gate is still enforced, no covert action. "Credential access" and URL findings are documentation prose / example/localhost URLs, same as prior scans.

## mcp-exfil-scan — MCP exfiltration scan
**Summary:** Risk 0/100 — CLEAN. No tool description poisoning, no suspicious outbound flow, no exfil chains, no encoded payloads, no env var leaking across 5 MCP configs / 10 skill files.

## Cross-Tool Observations
- Trivy and OSV-Scanner independently confirm the same 3 HIGH `mcp` CVEs — high-confidence real finding, fixed this run.
- Gitleaks, TruffleHog, and Semgrep-secrets all independently report **zero secrets**.
- mcps-audit and skill-audit again both flag the CDP cookie-extraction scripts/docs — consistent false-positive pattern rooted in the tool's legitimate purpose, not independent corroboration of a real issue.
- No overlap between config-audit and mcp-exfil-scan on any actual MCP server definition in this repo.

## Coverage Gaps
- Not covered: business logic correctness, IDOR/authorization logic beyond static pattern matching, runtime behavior.
- CodeQL skipped — no CodeQL GitHub Actions workflow configured.
- mcp-scan and skillspector LLM mode skipped (opt-in, third-party data send) — not requested this run.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260717T041057Z.jsonl`
- **Tool runs recorded:** 14 (measured: 2, asserted: 12)
- **Standard:** OWASP APTS § Auditability

## Conclusion
One real HIGH finding this run — `mcp` 1.27.0 (3 CVEs, cross-confirmed by Trivy + OSV-Scanner) — **fixed** by upgrading to 1.28.1 via `uv lock --upgrade-package mcp` + `uv sync`; full test suite still passes (1150 passed). All other Medium/High/Critical signals (mcps-audit, skill-audit, config-audit) are heuristic false positives against this project's documented, intentional CDP-based cookie extraction feature, consistent with prior scan history. Bandit's 75 Medium findings are confined to test fixtures. Secret scanning (Gitleaks, TruffleHog, Semgrep) is clean.

Per user instruction, remaining Low/Info findings were not fixed this run.
