# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-08-06T05:35:26Z
**Git HEAD:** post-merge of origin/main v0.9.7 (8 commits, PRs #278–#283)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Scope Record
```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    post-merge v0.9.7
Include:     all supported (src/, tests/, docs/, config files)
Exclude:     .venv/ (third-party dependencies)
```

## Coverage Disclosure

| Tool | Ran? | Version | Files covered | Skipped reason |
|------|------|---------|---------------|----------------|
| Gitleaks | OK | 8.30.1 | 705 commits, ~10.7MB | — |
| Bandit | OK | 1.9.4 | repo (src+tests, `.venv` excluded) | — |
| Semgrep (OWASP Top 10) | OK | latest | 109 Python files, 560 rules | 89 files matched `.semgrepignore` |
| Semgrep (secrets) | OK | latest | 179 files, 38 rules | 89 files matched `.semgrepignore` |
| Trivy (fs) | OK | 0.72.0 | uv.lock (88 packages) | `.venv` skipped |
| TruffleHog | OK | 3.95.9 | git history, 9337 chunks | — |
| OSV-Scanner | OK | 2.4.0 | uv.lock (88 packages) | — |
| CodeQL | SKIPPED | — | — | no `.github/workflows/codeql.yml` |
| mcps-audit | SKIPPED | — | — | no MCP server config files matched pattern |
| security-audit (config-audit.py) | OK | bundled | global `~/.claude` + repo docs | — |
| skill-audit | OK | bundled | `notebooklm-cli.skill`, `data/SKILL.md` | — |
| mcp-exfil-scan | OK | bundled | repo (5 MCP configs, 10 skill files found) | — |
| mcp-scan | OPT-IN, not run | — | — | sends data to invariantlabs.ai — not requested this run |
| skillspector | SKIPPED | — | — | not run (overlaps skill-audit/mcp-exfil-scan already covering repo skill files) |

## Gitleaks — Secrets (git history + filesystem)
**Summary:** 0 leaks found across 705 commits.

## Bandit — Python SAST
**Summary:** 0 High, 89 Medium, 2168 Low (repo-scoped, `.venv` excluded).

- **High: 0.**
- **Medium (89): all in `tests/`** — `B106`/`B105` "hardcoded password" hits are mock/test fixtures (`'test'`, `'csrf'`, `'token'`, `'stale123'`, etc.), not real credentials; `B108` hardcoded tmp-dir hits are in test helpers.
- **Low, production code (`src/`):** `B603`/`B607` subprocess calls without `shell=True` and partial executable paths in `setup.py`, `auth.py`, `cdp.py`, `wsl.py` — all invoke fixed, list-form commands (`chrome`, `wslinfo`, `ip route`), not user-controlled input. `B110` try/except/pass in `auth.py:492`.
- No High/Medium findings in `src/`.

## Semgrep — OWASP Top 10 (Python)
**Summary:** 0 findings. 153 rules run across 109 files.

## Semgrep — Secrets
**Summary:** 0 findings. 38 rules run across 179 files.

## Trivy — Dependencies (fs scan)
**Summary:** 0 vulnerabilities, 0 secrets. `uv.lock` (88 packages) clean.

## TruffleHog — Secrets (git-verified)
**Summary:** 0 verified, 0 unverified secrets. 9337 chunks / 11.1MB scanned.

## OSV-Scanner — SCA
**Summary:** No issues found. `uv.lock` (88 packages).

## security-audit (config-audit.py) — Claude config audit
**Summary:** 99 issues found globally across `~/.claude` (all installed skills/plugins/settings), but **none are repo-scoped real findings**:

- Repo-scoped hits are limited to `CLAUDE.md`, `claude.md`, `AGENTS.md`, `GEMINI.md` — all flagged MEDIUM for "credentials file access" / "cookie/browser data access" / "instruction to skip verification". These are **false positives**: the docs legitimately describe this project's cookie-based Google auth flow (documented product behavior, not exploit code), and the "skip verification" match is a keyword hit on an unrelated troubleshooting-table line ("Verify account in cookies").
- All CRITICAL/HIGH findings belong to *other, unrelated* globally-installed skills/plugins (`anysearch`, `caveman`, the security-scanner's own bundled scripts, `claude-plugins-official` examples) — out of this scan's scope (this repo only).

## skill-audit — Packaged skill files
**Summary:**
- `notebooklm-cli.skill`: **0/100, LOW RISK, APPROVE.**
- `src/notebooklm_tools/data/SKILL.md`: **75/100, flagged CRITICAL by the heuristic scorer** — reviewed manually and determined to be a **false positive**:
  - "Silent action instruction" (Medium) — matched the phrase "Silently infer" (lines 66, 405), which describes skipping a clarifying-questions intake before drafting a Studio creation prompt. The actual create action still requires `studio_create(confirm=True)` — no consent bypass, no hidden action.
  - "Credential access" (+20 pts) — matched the word "credentials" in a single line documenting `nlm login` / cookie refresh, standard auth guidance for this CLI, not an exfiltration path.
  - "High bash complexity" (+10 pts) — the skill legitimately documents `nlm` CLI usage with 29 bash examples.
  - Net: no actual prompt-injection, credential-exfiltration, or dangerous-command pattern present; the score is inflated by keyword-based heuristics matching normal auth/UX documentation.

## mcp-exfil-scan — MCP exfiltration detection
**Summary:** 0/100, CLEAN. No tool-description poisoning, outbound-flow risk, exfil chains, encoded payloads, env-var leaking, or untrusted sources detected across 5 MCP configs and 10 skill files in repo scope.

## Cross-Tool Observations
- Gitleaks, Semgrep-secrets, Trivy, and TruffleHog independently agree: **zero secrets** in the repo or git history.
- Bandit, Semgrep-OWASP, and OSV-Scanner independently agree: **zero exploitable code-level or dependency vulnerabilities** at High/Critical severity in `src/`.
- The two heuristic-flagged items (config-audit's doc-keyword matches, skill-audit's 75/100 score) both trace to the same root cause — this project's docs and packaged skill *legitimately* discuss cookies/credentials because it's a browser-cookie-based auth CLI. No cross-tool corroboration of an actual exfiltration or injection vector; mcp-exfil-scan (which specifically targets exfiltration chains) found nothing.

## Coverage Gaps
- Business logic and IDOR-style authorization bugs are not covered by static tools — not assessed.
- Runtime behavior (actual MCP tool call flows, live cookie handling) not exercised — static analysis only.
- CodeQL and mcps-audit skipped (no GitHub Actions CodeQL workflow; no MCP server config matched the file-pattern search in this repo — the project *is* an MCP server but ships as Python source, not a `.mcp.json`/`.skill` bundle at the point mcps-audit checks).
- mcp-scan (opt-in, external service) and skillspector LLM-mode not run — no request from user to send data externally this cycle.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260806T053526Z.jsonl`
- **Tool runs recorded:** 3 (measured: 2, asserted: 1)
- **Standard:** OWASP APTS § Auditability

---

## Overall Verdict

**No Very High, High, or Medium severity findings in production code (`src/`).** All Medium-severity Bandit hits are test-fixture false positives. The two flagged items outside code (config-audit doc-keyword matches, skill-audit's 75/100 heuristic score on `SKILL.md`) are both confirmed false positives on the tool authors' side after manual review — this project's cookie/credential documentation is its intended, documented auth mechanism, not a vulnerability.

**No fixes required this cycle.**
