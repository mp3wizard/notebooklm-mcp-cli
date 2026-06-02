# Security Scan Report — 2026-06-02

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-06-02T02:42Z
**Git HEAD:** 36bbda4 (post-merge v0.6.15)
**Trigger:** Daily upstream sync — v0.6.13 → v0.6.15 (13 commits merged)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Upstream Changes Merged

| Version | PRs / Issues | Key Changes |
|---------|-------------|-------------|
| v0.6.15 | PR #212, Issue #213 | Auth-guard stale-TTL fix (all profile cookies watched); services/auth.py full shim |
| v0.6.14 | PR #211, PR #212 | nlm login crash fix; MCP silent auth/studio failures; bounded conversation cache |

## Tool Coverage

| Tool | Version | Status | Findings in project source |
|------|---------|--------|---------------------------|
| Gitleaks | 8.30.1 | OK | 0 |
| Bandit | 1.9.4 | OK | 0 (22 High all in .venv third-party) |
| Semgrep OWASP | current | OK | 0 |
| Semgrep Python | current | OK | 0 |
| Semgrep Secrets | current | OK | 0 |
| Trivy | 0.69.3 | OK | 0 |
| TruffleHog | 3.94.2 | OK | 0 verified, 0 unverified |
| OSV-Scanner | 2.3.5 | OK | 0 |
| mcps-audit | 1.0.0 | OK | 480 findings (all in dev scripts / false positives) |
| security-audit | bundled | OK | 43 findings (all false positives or out-of-scope) |
| skill-auditor | bundled | OK | notebooklm-cli.skill: 0/100 LOW RISK |
| mcp-exfil-scan | bundled | OK | 11 findings (all in user global skills, out of project scope) |
| CodeQL | — | SKIPPED | No .github/workflows/codeql.yml |
| mcp-scan | — | OPT-IN | Not run |

## Vulnerability Summary

| Severity | Count | Status |
|----------|-------|--------|
| Very High | 0 | — |
| High | 0 (project source) | Clean |
| Medium | 0 (project source) | Clean |
| Low | multiple (test files / .venv) | Accepted, not fixed |
| Info | — | — |

## Dependency Scan (uv.lock — 89 packages)

**Trivy:** 0 vulnerabilities
**OSV-Scanner:** 0 issues

No dependency upgrades required.

## Key Findings Analysis

### Bandit High Severity (22 findings)
All in `.venv/` third-party libraries:
- `authlib`: B324 SHA1 use (OAuth1 signature — protocol requirement)
- `cryptography`: B324 SHA1 in X.509 extension parsing
- `dns`: B324 SHA1/MD5 in DNSSEC (protocol requirement)
- `requests`: B324 SHA1 in Digest auth (protocol requirement)
- `websocket`: B602 shell=True (websocket-client lib)
- `fastmcp`, `mcp`, `mypy`, `pygments`, `jaraco`: various B-codes

**No High/Medium findings in `src/notebooklm_tools/`** ✅

### mcps-audit (480 findings, 100/100 risk)
Score is inflated due to:
- `AS-001` "Dangerous execution" in `scripts/inject_cookies_and_inspect.py` — CDP JavaScript injection for browser inspection. Development script, not production MCP.
- `AS-010` "No logging" in dev scripts — expected for utility scripts.
- `MCPS SDK: not found` — project uses FastMCP, not official MCPS SDK.
- Production MCP code (`src/notebooklm_tools/mcp/`): no specific critical findings.

### config-audit (5 Critical, 10 High)
- Critical: `security-scanner` and `skill-security-auditor` skills flagged — self-referential false positive (scanner tools contain words "base64" and "exfiltrate" in their own documentation).
- High: cc-beeper hooks (`curl http://localhost:${PORT}/hook`) — user's local notification system, localhost only.
- Medium: CLAUDE.md cookie/credential references — expected for a cookie-based auth CLI project.

### mcp-exfil-scan (2 Critical, 5 High, 4 Medium)
- All findings are in `~/.claude/skills/*` (user global config) — out of project scope per APTS Scope Enforcement.
- This project's skill files (`notebooklm-cli.skill`, `data/SKILL.md`): not flagged.

## Skill Security Scores

| Skill | Score | Verdict |
|-------|-------|---------|
| notebooklm-cli.skill | 0/100 | LOW RISK ✅ APPROVE |
| data/SKILL.md (nlm-skill) | 35/100 | MEDIUM RISK — APPROVE WITH CAUTION |

`data/SKILL.md` score driven by: 6 example/placeholder URLs (`example.com`, `youtube.com/...`, `127.0.0.1`), 7 file operations (CLI documentation). No credential access, no prompt injection patterns.

## Fixes Applied

None required — project source is clean.

## Overall Risk Posture

**CLEAN** ✅

The merged v0.6.14–0.6.15 changes actively improve security posture:
- Auth failures now fail loudly instead of silently
- Stale auth TTL window closed for all profiles
- Conversation cache bounded to prevent OOM

APTS Audit Log: `/tmp/css-scan-20260602T023806Z.jsonl` (16 tool runs recorded)
