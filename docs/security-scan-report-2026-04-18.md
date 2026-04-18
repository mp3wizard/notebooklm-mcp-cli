# Security Scan Report — notebooklm-mcp-cli v0.5.26

**Date:** 2026-04-18  
**Trigger:** Post-merge upstream sync (origin/main → local main)  
**Merged commits:** `a434adf` (v0.5.26 release), `6a62ec3` (CHANGELOG credits)  
**Tools:** Gitleaks 8.30.1, Bandit 1.9.4, Semgrep (latest), Trivy 0.69.3, TruffleHog 3.94.2, OSV-Scanner 2.3.5, mcps-audit, config-audit, skill-audit, mcp-exfil-scan

---

## Summary

| Category | Result |
|----------|--------|
| Secrets in git history | ✅ Clean (Gitleaks + TruffleHog) |
| Python SAST (src/) | ✅ Clean (Bandit 0 H/M/L, Semgrep 0 findings) |
| Dependency vulnerabilities | ✅ Fixed (authlib 1.6.9 → 1.6.11) |
| IaC / container misconfig | ✅ Clean (Trivy) |
| MCP skill audit | ✅ Low Risk (skill-audit) |
| Config/MCP exfil scan | ⚠️ False positives only (see notes) |

---

## Findings

### Fixed — Medium

| Package | Old | New | Advisory | CVSS |
|---------|-----|-----|----------|------|
| authlib | 1.6.9 | 1.6.11 | GHSA-jj8c-mmj3-mmgv | 5.4 |

**authlib GHSA-jj8c-mmj3-mmgv** — Token/cookie confusion vulnerability in OAuth/OIDC flows. Fixed by upgrading to 1.6.11 via `uv lock --upgrade-package authlib && uv sync`.

### Fixed — Low (Bandit nosec annotations)

| File | Line | Rule | Justification |
|------|------|------|---------------|
| `core/conversation.py` | 247, 250 | B101 assert | Type-narrowing only — conversation_id always set by preceding control flow |
| `services/studio.py` | 322 | B101 assert | Dead code — `_validate_result()` already raises ServiceError on None result |
| `services/studio.py` | 622 | B110 try/except pass | Intentional — mind map parsing is optional |
| `utils/wsl.py` | 220, 231, 240 | B603 B607 subprocess | Fixed Windows/WSL system paths: `powershell.exe`, `wslpath` — no user input |

---

## Tool Results

### Gitleaks — 477 commits scanned
**Result:** No leaks found

### Bandit — 21,471 lines (src/ only)
**Result after fixes:** 0 High, 0 Medium, 0 Low  
(43 nosec suppressions total across codebase — all pre-existing + 5 new this run)

### Semgrep
- OWASP Top 10: 153 rules, **0 findings**
- Python: 151 rules, **0 findings**
- Secrets: 37 rules, **0 findings**

### Trivy (uv.lock)
**Result:** 0 vulnerabilities in 88 packages

### TruffleHog
**Result:** 0 verified secrets, 0 unverified secrets

### OSV-Scanner (uv.lock)
**Before:** 1 Medium (authlib 1.6.9, GHSA-jj8c-mmj3-mmgv)  
**After:** No issues found

### Skill Audit
- `notebooklm-cli.skill`: Risk score **0/100** — LOW RISK
- `src/.../data/SKILL.md`: Risk score **35/100** — MEDIUM (documentation examples, no executable code)

### mcps-audit / config-audit / mcp-exfil-scan
**Notes — False Positives Only:**
- mcps-audit CRITICAL in `scripts/inject_cookies_and_inspect.py` and `inspect_upload_dom.py`: These files intentionally contain JavaScript strings for CDP browser injection — not arbitrary code execution
- config-audit CRITICALs: Security scanner tools flagging their own detection patterns (`base64`, `exfiltrate`, `ncat` in scanner source code)
- mcp-exfil-scan CRITICALs/HIGHs: `skill-security-auditor` and `security-scanner` skills legitimately reference external URLs and use broad tools (Bash, WebFetch) — this is expected for security tooling
- CLAUDE.md "credentials/cookies" references: Project explicitly handles Google auth cookies — expected

---

## Coverage Gaps

- **CodeQL**: Not run — no `.github/workflows/codeql.yml` in this fork
- **mcp-scan (invariantlabs.ai)**: Not run — opt-in only, requires sending data to external service
- **Business logic**: Not covered by automated tooling
- **Runtime behavior**: Not covered
