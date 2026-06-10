# Security Scan Report — 2026-06-10

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-06-10T02:43Z
**Git HEAD:** d35cabc (post-merge v0.7.3)
**Trigger:** Daily upstream sync — v0.7.0 to v0.7.3 (23 commits merged)
**Standard:** OWASP APTS-aligned (Scope Enforcement, Auditability, Manipulation Resistance, Reporting)

## Upstream Changes Merged

| Version | Key Changes |
|---------|-------------|
| v0.7.1 (b43cb5a) | Robust multi-probe AuthHealthChecker with header fix (#219); no_proxy sanitization on import to prevent httpx crash on Windows |
| v0.7.2 (05d2852) | Profile-aware headless auth refresh (#223); modern Chrome profile DB path detection (#222); full cookie list in AuthHealthChecker API fallback |
| v0.7.3 (6d41c75) | Unified MCP auth gates for semi-stale cookies (#224, #225); ruff formatting fixes; CLI_GUIDE.md Scripting and Automation section |

**Note:** ChatGPT artifact download/upload bridge was added in development (PRs #220, #221) but removed in v0.7.3 release — not present in final codebase.

## Merge Conflict Resolution

- **CLAUDE.md**: Conflict between local HEAD (Test Structure section) and upstream (MCP Tools Provided table with source_add_chatgpt_file). Resolved by keeping local HEAD — upstream table referenced source_add_chatgpt_file which was removed in v0.7.3. Correct resolution.

## Tool Coverage

| Tool | Version | Status | Findings in project source |
|------|---------|--------|---------------------------|
| Gitleaks | 8.30.1 | OK | 0 |
| TruffleHog | 3.94.2 | OK | 0 verified, 0 unverified |
| Bandit | 1.9.4 | OK | 0 High; 74 Medium B108 in tests (false positives); 1 Medium B102 in test (false positive) |
| Semgrep OWASP | current | OK | 0 |
| Semgrep Python | current | OK | 0 |
| Semgrep Secrets | current | OK | 0 |
| Trivy | 0.69.3 | OK | 0 CVEs (89 packages scanned) |
| OSV-Scanner | 2.3.5 | OK | 0 issues (uv.lock clean) |
| config-audit | bundled | OK | 43 findings (all false positives) |
| mcp-exfil-scan | bundled | OK | 0 findings in project |

## Findings Analysis

All tools returned clean results for the project source code:

- **Dependencies:** No CVEs in any of 89 packages in uv.lock
- **Secrets:** No secrets detected in git history (595 commits) or filesystem
- **SAST:** Semgrep OWASP/Python/Secrets returned 0 findings across 97 files
- **Bandit Medium B108:** 74 hardcoded /tmp/ references all in tests/ — test fixtures only; acceptable
- **Bandit Medium B102:** exec() in tests/services/test_auth_service.py:150 is an import-verification test; false positive
- **config-audit CRITICAL/HIGH:** All flag the security scanner's own scripts; user's cc-beeper localhost hooks are not a threat

### Previous Fixes Still Holding

- pyjwt CVEs from v0.7.0 scan remain fixed (pyjwt 2.10.1+ in uv.lock)
- TOCTOU-safe credential file creation (v0.6.13) — still present
- CDP origin restriction to localhost (v0.5.17) — still present
- HTTP/SSE external-bind enforcement — still present

## Verdict

CLEAN — No security fixes required for v0.7.3 merge. Project maintains the same strong security posture as previous scans.

## Next Steps

- Await user confirmation to commit merge and push to mywizard remote
- Reinstall with uv tool install --force . after push (Phase 4d)
