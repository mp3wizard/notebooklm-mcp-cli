# Security Scan Report — notebooklm-mcp-cli v0.5.27

**Date:** 2026-04-22  
**Trigger:** Post-merge upstream sync (origin/main → local main)  
**Merged commits:** `acadaf7` (fix source --title, PR #162), `b44546d` (fix skill targets #163), `7ed0392` (v0.5.27 release), `befae75` (formatting fix)  
**Tools:** Gitleaks 8.30.1, Bandit 1.9.4, Semgrep (latest), Trivy 0.69.3, TruffleHog 3.94.2, OSV-Scanner 2.3.5, config-audit, mcp-exfil-scan

---

## Summary

| Category | Result |
|----------|--------|
| Secrets in git history | ✅ Clean (Gitleaks + TruffleHog) |
| Python SAST (src/) | ✅ Clean (Bandit 0 H/M; Semgrep 0 findings) |
| Dependency vulnerabilities | ✅ Fixed (python-dotenv 1.2.1 → 1.2.2) |
| IaC / container misconfig | ✅ Clean (Trivy) |
| Config/MCP exfil scan | ⚠️ False positives only (see notes) |

---

## Findings

### Fixed — Medium

| Package | Old | New | Advisory | CVSS |
|---------|-----|-----|----------|------|
| python-dotenv | 1.2.1 | 1.2.2 | CVE-2026-28684 / GHSA-mf9w-mj56-hr94 | 6.6 |

**python-dotenv CVE-2026-28684** — Fixed by upgrading to 1.2.2 via `uv lock --upgrade-package python-dotenv && uv sync`. Confirmed clean by OSV-Scanner post-upgrade.

---

## Tool Results

### Gitleaks — 483 commits scanned
**Result:** No leaks found

### Bandit — src/ only
**Result:** 0 High, 0 Medium, 0 Low  
(53 nosec suppressions total across codebase — all pre-existing)

Note: Full scan including `.venv/` reports 22 High / 179 Medium — all in third-party packages. Not actionable for this project.

### Semgrep
- OWASP Top 10: 153 rules, **0 findings**
- Python: 151 rules, **0 findings**
- Secrets: 38 rules, **0 findings**

### Trivy (uv.lock — skipping .venv)
**Before:** 1 Medium (python-dotenv 1.2.1, CVE-2026-28684)  
**After (post-fix):** No vulnerabilities

### TruffleHog
**Result:** 0 verified secrets, 0 unverified secrets (6,858 chunks / 9.3 MB scanned)

### OSV-Scanner (uv.lock)
**Before:** 1 Medium (python-dotenv 1.2.1, GHSA-mf9w-mj56-hr94, CVSS 6.6)  
**After:** No issues found

### config-audit / mcp-exfil-scan
**Notes — False Positives Only:**
- config-audit CRITICALs: Security scanner tools flagging their own detection patterns (`base64`, `exfiltrate`, `ncat` in scanner source code)
- mcp-exfil-scan CRITICALs/HIGHs: `skill-security-auditor` and `security-scanner` skills legitimately reference external URLs and use broad tools (Bash, WebFetch) — expected for security tooling
- CLAUDE.md "credentials/cookies" references: Project explicitly handles Google auth cookies — expected per design

---

## Coverage Gaps

- **CodeQL**: Not run — no `.github/workflows/codeql.yml` in this fork
- **mcp-scan (invariantlabs.ai)**: Not run — opt-in only, requires sending data to external service
- **Business logic**: Not covered by automated tooling
- **Runtime behavior**: Not covered

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260422T023804Z.jsonl`
- **Tool runs recorded:** 7
- **Standard:** OWASP APTS § Auditability
