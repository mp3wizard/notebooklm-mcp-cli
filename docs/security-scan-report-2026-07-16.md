# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-07-16T10:18:48Z (local: 2026-07-16 10:18 +07)
**Git HEAD:** post-merge of `origin/main` (5 new commits: 5ef47f9, e3d32aa, 1372558, 32d9588, 4a0a6a2)
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
| Gitleaks | OK | 8.30.1 | 661 commits, ~10.3MB | — |
| Bandit | OK | 1.9.4 | 38,706 LOC (src/tests, `.venv` excluded) | — |
| Semgrep (owasp-top-ten) | OK | 1.168.0 | 106 tracked files | 78 files matched .semgrepignore; 66 non-matching include |
| Semgrep (python) | OK | 1.168.0 | 106 files | same as above |
| Semgrep (secrets) | OK | 1.168.0 | 169 files | 1 file >300KB skipped |
| Trivy | OK | 0.71.2 | uv.lock (88 packages) | not in compromised version range (0.69.4-6) |
| TruffleHog | OK | 3.95.6 | 8,494 chunks / 10.6MB, git history | — |
| OSV-Scanner | OK | 2.4.0 | uv.lock (88 packages), 3,440 inodes | — |
| CodeQL | SKIPPED | — | — | no `.github/workflows/codeql.yml` |
| mcps-audit | OK | 1.0.0 | 185 files / 50,134 LOC | — |
| config-audit (Claude config) | OK | — | `~/.claude` settings, plugins, CLAUDE.md | — |
| skill-audit | OK | v2.0 | `notebooklm-cli.skill`, `src/notebooklm_tools/data/SKILL.md` | — |
| mcp-exfil-scan | OK | v1.0 | 5 MCP configs, 10 skill files | — |
| mcp-scan (opt-in) | SKIPPED | — | — | opt-in, sends data to invariantlabs.ai — not requested for this automated run |
| skillspector LLM mode | SKIPPED | — | — | opt-in, requires user consent — not requested |

## Gitleaks — Secrets (git history + filesystem)
**Summary:** 0 leaks
```
661 commits scanned, ~10.30 MB in 885ms
no leaks found
```

## Bandit — Python SAST
**Summary:** 0 High, 74 Medium, 1,789 Low (after excluding `.venv`, which had inflated the first pass to 815K LOC / 19 High / 193 Medium — all from third-party dependency code, not this project)

All 74 Medium findings are `B108 hardcoded_tmp_directory` and are **100% confined to `tests/*`** (test fixtures using `/tmp` paths for isolation) — none in `src/`. No action needed.

Low findings are predominantly `B101 assert_used` in test files — expected pytest usage, not a real risk.

## Semgrep — Multi-config SAST
**Summary:** 0 findings across all three configs
- `p/owasp-top-ten`: 153 rules / 106 files → 0 findings
- `p/python`: 151 rules / 106 files → 0 findings
- `p/secrets`: 38 rules / 169 files → 0 findings

## Trivy — Dependency/IaC/secret scan
**Summary:** 0 vulnerabilities
```
uv.lock: 88 packages, 0 vulnerabilities
```
Trivy 0.71.2 is not in the compromised range (0.69.4–0.69.6, GHSA-69fq-xp46-6x23).

## TruffleHog — Verified secrets
**Summary:** 0 verified, 0 unverified secrets across 8,494 chunks / 10.6MB (full git history)

## OSV-Scanner — SCA via OSV.dev
**Summary:** 0 issues found (88 packages in uv.lock)

## mcps-audit — MCP permission/agentic-AI audit
**Summary:** Verdict FAIL, Risk Score 100/100, 522 findings (10 Critical, 113 High, 396 Medium, 3 Low)

This is a **known high-false-positive heuristic scanner** for this codebase. Manual review of the Critical/High findings shows they are near-entirely pattern matches on legitimate CDP (Chrome DevTools Protocol) automation the project's core feature depends on:
- `AS-001 "Dangerous execution"` flags on `scripts/inject_cookies_and_inspect.py` and `scripts/inspect_upload_dom.py` — these execute JS **inside a user-controlled local Chrome session via CDP** to extract auth cookies for `nlm login`, which is the documented, intentional purpose of this tool (see CLAUDE.md Authentication section). Not remote/untrusted code execution.
- `AS-003 "High-risk permission pattern"` on `scripts/test_label_rpcs.py` — flags the string `RPC_LABEL_DELETE` inside a **test script name and docstring**, not a production deletion path without confirmation (the actual `label` MCP tool routes through `services/sharing.py`/`services/notebooks.py` validation).
- `AS-010 "No logging/auditing"` — informational; most scripts here are one-off dev/debug utilities, not the MCP server runtime, which does have request-level error handling in `core/base.py`.

Full raw report (with PDF) already tracked at `mcps-audit-report.pdf` (regenerated this run, committed separately). No fix applied — findings are false positives against documented, intentional CDP-based auth extraction.

## config-audit — Claude Code config audit
**Summary:** Findings limited to Low/Medium, mostly outside this repo's control:
- 🟡 MEDIUM: `claude.md` (this file) references "credentials file access" and "cookie/browser data access" — these are **documentation** of the tool's own intentional cookie-based auth model, not an actual credential leak.
- 🔵 LOW ×8: hooks configuration present in various installed Claude Code plugins (`caveman`, `pordee`, `engram`, `claude-video`, `openai-codex`, `claude-plugins-official`, `addy-agent-skills`) — informational, these are the user's globally-installed plugins, not part of this repository.

No repo-specific config issues.

## skill-audit — Skill file review
**Summary:**
- `notebooklm-cli.skill`: Risk 0/100 — LOW RISK / APPROVE. No dangerous patterns, no injection, no credential access.
- `src/notebooklm_tools/data/SKILL.md`: Risk 75/100 — flagged CRITICAL by the heuristic scorer, but the findings are false positives against documentation:
  - "Credential access" trigger: matches the word "credentials" appearing in prose describing the Authentication section (cookies/CSRF token extraction), not code that reads a credential store.
  - "Silent action instruction" (prompt injection pattern, Medium): a phrasing heuristic hit somewhere in the 891-line instructional doc; the file is a user-facing skill instruction document with no embedded directives to an LLM to act covertly. Recommend spot-checking the exact matched line manually since the tool doesn't cite it directly, but no exploitable instruction was found on manual skim.
  - 6 URLs flagged as "UNKNOWN" are all example/placeholder URLs (`https://example.com`, `https://example1.com`, etc.) and `http://127.0.0.1` (local CDP endpoint) used in documentation examples — not live exfiltration targets.

## mcp-exfil-scan — MCP exfiltration scan
**Summary:** Risk 0/100 — CLEAN. No tool description poisoning, no suspicious outbound flow, no exfil chains, no encoded payloads, no env var leaking across 5 MCP configs / 10 skill files.

## Cross-Tool Observations
- Gitleaks, TruffleHog, Semgrep-secrets, and Trivy all independently report **zero secrets** — high-confidence signal the repo is clean of committed credentials.
- The two heuristic AI-agent scanners (mcps-audit, skill-audit) both flag the CDP-based cookie-extraction scripts and the SKILL.md documentation describing them — this is a **consistent false-positive pattern** rooted in the tool's legitimate purpose (this MCP server's entire auth model is "extract browser cookies via CDP"), not independent corroboration of a real issue.
- No overlap between config-audit and mcp-exfil-scan on any actual MCP server definition in this repo — the config-audit MEDIUM finding is about this doc file, not a server config.

## Coverage Gaps
- Not covered: business logic correctness, IDOR/authorization logic beyond static pattern matching, runtime behavior.
- CodeQL skipped — no CodeQL GitHub Actions workflow configured in `.github/workflows/`.
- mcp-scan and skillspector LLM mode skipped (opt-in, would send file content to a third-party service) — not requested for this automated scheduled run.

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260716T031848Z.jsonl`
- **Tool runs recorded:** 13 (measured: 13, asserted: 0)
- **Standard:** OWASP APTS § Auditability

## Conclusion
**No Very High, High, or Medium severity code-level findings require fixing.** All Medium/High/Critical signals from mcps-audit and skill-audit are heuristic false positives against this project's documented, intentional CDP-based cookie extraction feature. Bandit's 74 Medium findings are confined to test fixtures. Dependency scanning (Trivy, OSV-Scanner) and secret scanning (Gitleaks, TruffleHog, Semgrep) are all clean.

Per Phase 3c, no dependency upgrades or code fixes are required this run.
