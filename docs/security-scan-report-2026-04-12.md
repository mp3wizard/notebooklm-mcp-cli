# Automated Security Scan Report

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-04-12T09:40–09:43+07:00
**Post-merge version:** v0.5.22
**Tools run:** Gitleaks 8.30.1, Bandit 1.9.4, Semgrep 1.157.0, Trivy 0.69.3, TruffleHog 3.94.2, OSV-Scanner 2.3.5, config-audit (bundled), skill-audit (bundled), mcp-exfil-scan (bundled)
**Tools skipped:** CodeQL (no codeql.yml workflow), mcps-audit (no additional MCP configs), mcp-scan (opt-in, not consented)

---

## Pre-flight Summary

| Tool | Status | Version |
|------|--------|---------|
| Gitleaks | OK | 8.30.1 |
| Bandit | OK | 1.9.4 |
| Semgrep | OK | 1.157.0 |
| Trivy | OK | 0.69.3 |
| TruffleHog | OK | 3.94.2 |
| OSV-Scanner | OK | 2.3.5 |
| gh (CodeQL) | OK | — (no codeql.yml, skipped) |
| npx (mcps-audit) | OK | — (no MCP configs in project, skipped) |
| uvx (mcp-scan) | OK | opt-in only |
| config-audit.py | OK | bundled |
| skill-audit.sh | OK | bundled |
| mcp-exfil-scan.sh | OK | bundled |

---

## Gitleaks — Secrets in Git History

**Summary:** 0 leaks found. 439 commits scanned, ~8.86 MB.

```
439 commits scanned.
scanned ~8863007 bytes (8.86 MB) in 1.23s
no leaks found
```

---

## Bandit — Python SAST (src/ + tests/)

**Summary:** 0 High, 51 Medium, 1150 Low issues found. All findings are False Positives or in test code.

**Medium (51 total):**
- `B107/B105 hardcoded_password_*` — All false positives: empty string defaults for optional auth params (`csrf_token=""`, `session_id=""`), and a message string containing the word "CSRF token". The empty defaults are intentional — tokens are auto-extracted at runtime.
- No actual hardcoded credentials or secrets found.

**Low (1150 total):**
- `B404/B603 subprocess` — All legitimate subprocess calls in `setup.py` and `doctor.py` for running `claude mcp add/remove/list` and `pbcopy`. All use list form (no shell injection risk).
- `B607 start_process_with_partial_path` — `pbcopy` on macOS (platform-specific, acceptable).
- `B101 assert_used` — In test files and `retry.py` (unreachable code guard, not a security risk).
- `B105 hardcoded_password_string` — False positive: string "Force re-extraction of CSRF token" flagged as hardcoded password.

**Verdict:** No actionable findings. All Medium/Low issues are false positives or acceptable patterns.

---

## Semgrep — SAST (OWASP Top 10, Python, Secrets)

**Summary:** 0 findings across all three rule sets.

- OWASP Top 10: 0 findings (153 rules on 89 files)
- Python rules: 0 findings (151 rules on 89 files)
- Secrets: 0 findings (37 rules on 94 files)

---

## Trivy — Dependency Vulnerabilities (Pre-fix)

**Summary:** 16 vulnerabilities found BEFORE security fixes. **0 vulnerabilities after upgrade.**

### Pre-fix findings (now resolved):

| Package | CVE | Severity | Installed | Fixed | Status |
|---------|-----|----------|-----------|-------|--------|
| authlib | CVE-2026-27962 | CRITICAL | 1.6.6 | 1.6.9 | ✅ FIXED |
| fastmcp | CVE-2026-32871 | CRITICAL | 2.14.2 | 3.2.0 | ✅ FIXED |
| authlib | CVE-2026-28490 | HIGH | 1.6.6 | 1.6.9 | ✅ FIXED |
| authlib | CVE-2026-28498 | HIGH | 1.6.6 | 1.6.9 | ✅ FIXED |
| authlib | CVE-2026-28802 | HIGH | 1.6.6 | 1.6.7 | ✅ FIXED |
| cryptography | CVE-2026-26007 | HIGH | 46.0.3 | 46.0.5 | ✅ FIXED |
| fastmcp | CVE-2026-27124 | HIGH | 2.14.2 | 3.2.0 | ✅ FIXED |
| lupa | CVE-2026-34444 | HIGH | 2.6 | no fix | ✅ REMOVED (transitive dep dropped) |
| pyjwt | CVE-2026-32597 | HIGH | 2.10.1 | 2.12.0 | ✅ FIXED |
| python-multipart | CVE-2026-24486 | HIGH | 0.0.21 | 0.0.22 | ✅ FIXED |
| cryptography | CVE-2026-39892 | MEDIUM | 46.0.3 | 46.0.7 | ✅ FIXED |
| diskcache | CVE-2025-69872 | MEDIUM | 5.6.3 | no fix | ✅ REMOVED (transitive dep dropped) |
| fastmcp | CVE-2025-64340 | MEDIUM | 2.14.2 | 3.2.0 | ✅ FIXED |
| requests | CVE-2026-25645 | MEDIUM | 2.32.5 | 2.33.0 | ✅ FIXED |
| cryptography | CVE-2026-34073 | LOW | 46.0.3 | 46.0.6 | ✅ FIXED |
| pygments | CVE-2026-4539 | LOW | 2.19.2 | 2.20.0 | ✅ FIXED |

### Post-fix Trivy result:
```
uv.lock │ uv │ 0 │
```
**Clean — 0 vulnerabilities.**

---

## TruffleHog — Secrets with Live Verification

**Summary:** 0 verified secrets, 0 unverified secrets. 6366 chunks, 9,085,670 bytes scanned.

```
verified_secrets: 0, unverified_secrets: 0
scan_duration: "909.412916ms"
```

---

## CodeQL — Semantic SAST

**Skipped:** No `codeql.yml` workflow found in `.github/workflows/`.

---

## OSV-Scanner — SCA via OSV.dev (Pre-fix)

**Summary:** 17 vulnerabilities found across 10 packages before fixes. All resolved post-upgrade.

Additional finding not in Trivy:
- `jaraco-context 6.0.2` → GHSA-58pv-8j8x-9vj2 (CVSS 8.6, HIGH) → **Fixed: upgraded to 6.1.2**

---

## config-audit — Claude Code Security Audit

**Summary:** 21 issues found (5 CRITICAL, 5 HIGH, 9 MEDIUM, 2 LOW). All are false positives from the security tooling itself.

**False positive analysis:**
- `CRITICAL` flags on `security-scanner/SKILL.md`, `skill-security-auditor/SKILL.md`, `mcp-exfil-scan.sh`, `skill-audit.sh`, `config-audit.py` — These tools legitimately reference base64 encoding, SSH directories, and ncat patterns **as patterns to detect**, not as actual exfiltration. The scanner is flagging its own detection signatures.
- `HIGH` flags on `optimize/SKILL.md` (netcat reference) and `plugin-dev` hook examples (mkfs/dd patterns) — These are detection examples in hook validation scripts, not executable threats.
- `MEDIUM` flags on `CLAUDE.md`/`claude.md` — References to cookies and credentials are documentation (auth troubleshooting guide), not instruction to exfiltrate.
- `LOW` — Hooks configuration in plugin-dev (expected, legitimate pre-commit hooks).

**No actionable issues in the project codebase.**

---

## skill-security-auditor — Skill Files

**Summary:** 2 skill files scanned.

| File | Score | Verdict |
|------|-------|---------|
| `notebooklm-cli.skill` | 0/100 | LOW RISK — APPROVE |
| `src/notebooklm_tools/data/SKILL.md` | 35/100 | MEDIUM RISK — APPROVE WITH CAUTION |

`SKILL.md` score elevated due to: 6 example URLs (all placeholders: `example.com`, `youtube.com/...`, `127.0.0.1`), 7 file operation references (legitimate nlm CLI usage examples), and 27 bash code blocks (legitimate CLI usage documentation). No dangerous patterns or prompt injection found.

---

## mcp-exfil-scan — MCP Exfiltration Scan

**Summary:** 9 issues found (2 CRITICAL, 3 HIGH, 4 MEDIUM). All false positives from security tooling.

**False positive analysis:**
- `CRITICAL` — `extract/SKILL.md` and `security-audit/SKILL.md` flagged for "exfiltration instruction pattern" — these skills reference exfiltration as things they **scan for**, not perform.
- `HIGH` — `skill-security-auditor/SKILL.md` flagged for Read+WebFetch+Bash combination — expected for a security scanning tool; legitimate use.
- `MEDIUM` — `playwright-cli`, `pyright`, `vtsls` skills have no source attribution. Known tools, not supply chain risks.

**No exfiltration risks found in the project itself.**

---

## Cross-Tool Observations

1. **Dependency vulnerabilities** (Trivy + OSV-Scanner): High-confidence overlap confirming 16–17 CVEs across authlib, fastmcp, cryptography, pyjwt, python-multipart, requests, pygments, jaraco-context. All resolved by regenerating `uv.lock` from pyproject.toml constraints that origin already updated.

2. **No secrets in history**: Gitleaks and TruffleHog both clean across 439 commits — consistent, high confidence.

3. **No application-level SAST findings**: Bandit Medium/Low findings are all false positives; Semgrep 0 findings across OWASP/Python/Secrets. Clean application code.

4. **Config-audit and mcp-exfil-scan findings** are entirely from security tooling detecting its own patterns — expected behavior, not actionable.

---

## Fixes Applied

| Package | Before | After | CVEs Fixed |
|---------|--------|-------|------------|
| authlib | 1.6.6 | 1.6.9 | 4 (1 Critical, 3 High) |
| fastmcp | 2.14.2 | 3.2.3 | 3 (1 Critical, 1 High, 1 Medium) + removes diskcache/lupa |
| cryptography | 46.0.3 | 46.0.7 | 3 (1 High, 1 Medium, 1 Low) |
| pyjwt | 2.10.1 | 2.12.1 | 1 (High) |
| python-multipart | 0.0.21 | 0.0.26 | 1 (High) |
| requests | 2.32.5 | 2.33.1 | 1 (Medium) |
| jaraco-context | 6.0.2 | 6.1.2 | 1 (High) |
| pygments | 2.19.2 | 2.20.0 | 1 (Low) |

**Total CVEs resolved: 15 fixable + 2 unfixable (removed via transitive dep cleanup)**

---

## Coverage Gaps

- **Business logic / IDOR / runtime behavior**: Not covered by static analysis.
- **mcp-scan** (tool poisoning, prompt injection via MCP): Opt-in only — not run.
- **CodeQL**: No codeql.yml workflow present.
- **E2E tests with live auth**: Excluded from CI (`pytest -m "not e2e"`).
