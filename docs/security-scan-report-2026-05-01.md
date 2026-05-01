# Security Scan Report — 2026-05-01

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-05-01T12:09 ICT
**Git HEAD:** `10630d4` (post-merge v0.6.2)
**Triggered by:** Upstream sync — v0.6.1 (label reorganize) + v0.6.2 (login timeout #174 + headless browser hijacking fix)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

---

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    10630d4
Include:     all supported
Exclude:     .gitignore honored by each tool
```

---

## Coverage

| Tool | Status | Version | Files / Packages | Findings |
|------|--------|---------|------------------|----------|
| Gitleaks | ✅ Ran | 8.30.1 | 501 commits, 9.13 MB | 0 |
| Bandit | ✅ Ran (src/) | 1.9.4 | 22,312 LOC | 0 actionable |
| Semgrep OWASP | ✅ Ran | latest | 101 files, 153 rules | 0 |
| Semgrep Python | ✅ Ran | latest | 101 files, 151 rules | 0 |
| Semgrep Secrets | ✅ Ran | latest | 140 files, 38 rules | 0 |
| Trivy | ✅ Ran | 0.69.3 | uv.lock (88 pkgs) | 0 vulns / 0 secrets |
| TruffleHog | ✅ Ran (verified) | 3.94.2 | 7,005 chunks, 9.38 MB | 0 verified |
| OSV-Scanner | ✅ Ran | 2.3.5 | uv.lock (88 pkgs) | 0 |

---

## Merge Conflict Resolution

`src/notebooklm_tools/utils/cdp.py` had one conflict in the login-wait loop. Resolved by combining both improvements:
- **Local (HEAD):** SEC-007 transient-error logging (`_logger.debug` instead of bare `pass`) — kept
- **Upstream:** Periodic `Still waiting for sign-in...` status every 30s — added

Combined behavior: transient CDP poll failures are now logged at debug level **and** the user sees progress messages every 30s during sign-in wait.

---

## Findings by Severity

| Severity | Count | Action |
|----------|-------|--------|
| Very High | 0 | — |
| High | 0 | — |
| Medium | 0 | — |
| Low | 0 | — |
| Info | 0 | — |

**Overall risk posture: Clean.** No fixes required post-merge.

---

## Notes

- Trivy 0.69.3 confirmed not in compromised range (GHSA-69fq-xp46-6x23 affects 0.69.4–0.69.6). v0.70.0 is now available — non-blocking.
- `uv.lock` unchanged in this merge (no dependency churn).
- Ruff lint + format checks pass on 155 files.
