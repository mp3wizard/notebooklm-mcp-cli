# Security Scan Report — 2026-04-27

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)  
**Scanned at:** 2026-04-27T00:50 ICT  
**Git HEAD:** `1f61eb8` (post-merge v0.5.30)  
**Triggered by:** Upstream sync — v0.5.30 (fix stale NOTEBOOKLM_COOKIES auth loop #170)  
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

---

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    1f61eb8
Include:     all supported
Exclude:     .gitignore honored by each tool
```

---

## Coverage

| Tool | Status | Version | Files / Packages | Findings |
|------|--------|---------|-----------------|----------|
| Gitleaks | ✅ Ran | 8.30.1 | 489 commits, ~9 MB | 0 |
| Bandit | ✅ Ran (src/ only) | 1.9.4 | src/ | 0 actionable (2 suppressed — false positives) |
| Semgrep OWASP | ✅ Ran | 1.157.0 | 95 files, 153 rules | 0 |
| Semgrep Python | ✅ Ran | 1.157.0 | 95 files, 151 rules | 0 |
| Semgrep Secrets | ✅ Ran | 1.157.0 | 132 files, 38 rules | 0 |
| Trivy | ✅ Ran | 0.69.3 | uv.lock (88 pkgs) | 0 |
| TruffleHog | ✅ Ran | 3.94.2 | 6,924 chunks, 9.3 MB | 0 verified |
| CodeQL | SKIPPED | — | no codeql.yml in repo | — |
| OSV-Scanner | ✅ Ran | 2.3.5 | uv.lock (88 pkgs) | 0 |
| config-audit | ✅ Ran | bundled | project + global config | see below |
| skill-audit | ✅ Ran | bundled | 2 skill files | 0 / 35 score |
| mcp-exfil-scan | ✅ Ran | bundled | project MCP + skills | see below |
| mcp-scan | OPT-IN | — | not run (sends data to invariantlabs.ai) | — |

---

## Findings Detail

### Gitleaks — Secrets in Git History
**Summary:** 0 leaks. 489 commits scanned, ~9 MB.

### Bandit — Python SAST (src/ only)
**Summary:** 0 High, 0 Medium, 0 Low actionable. 2 false positives suppressed.

| ID | Location | Severity | Assessment |
|----|----------|----------|------------|
| B105 | `src/notebooklm_tools/mcp/tools/_utils.py:107` | Low | False positive — `csrf_token = ""` is a deprecated placeholder variable, not a password. Suppressed with `# nosec B105`. |
| B110 | `src/notebooklm_tools/services/sources.py:212` | Low | False positive — `try/except/pass` is intentional best-effort rename that must not mask upload success. Suppressed with `# nosec B110`. |

### Semgrep — OWASP / Python / Secrets
**Summary:** 0 findings across all 3 rulesets.

### Trivy — Dependency Vulnerabilities
**Summary:** 0 vulnerabilities in uv.lock (88 packages). 0 secrets.

### TruffleHog — Live-Verified Secrets
**Summary:** 0 verified secrets. 0 unverified. 6,924 chunks scanned.

### OSV-Scanner — SCA via OSV.dev
**Summary:** 0 issues in uv.lock (88 packages).

### config-audit — Claude Config & Project Audit
**Summary:** Findings are in global `~/.claude/settings.json` and installed skills — not in project code.

| Severity | Finding | Assessment |
|----------|---------|------------|
| HIGH | cc-beeper hooks use `curl` | ✅ Intentional — all connections to `localhost` only |
| HIGH | skill-security-auditor has Read+WebFetch+Bash | ✅ Intentional — security tool by design |
| MEDIUM | CLAUDE.md references cookies/credentials | False positive — legitimate authentication documentation |
| MEDIUM | CLAUDE.md "skip verification" | False positive — troubleshooting table entry, not an instruction |

### skill-audit — Skill Security Score
- `notebooklm-cli.skill` → **0/100 (LOW RISK)** ✅
- `src/notebooklm_tools/data/SKILL.md` → **35/100 (MEDIUM RISK)** — flagged for example URLs and bash complexity; no malicious patterns

### mcp-exfil-scan — MCP Exfiltration Chains
**Summary:** All findings are in global `~/.claude/skills/` — not in project source.
- CRITICAL/HIGH findings in `security-scanner`, `skill-security-auditor`, `atlas-cloud` skills are scanner tools by design.
- No outbound exfil chains detected in project code itself.

---

## Fixes Applied

| Fix | File | Action |
|-----|------|--------|
| Suppress B105 false positive | `src/notebooklm_tools/mcp/tools/_utils.py:107` | Added `# nosec B105 # deprecated placeholder, not a password` |
| Suppress B110 false positive | `src/notebooklm_tools/services/sources.py:212` | Added `# nosec B110 # best-effort rename, intentionally silent` |

No dependency upgrades required — uv.lock is clean.

---

## Overall Risk Posture

**🟢 CLEAN** — 0 vulnerabilities, 0 secrets, 0 SAST findings in project source code.

---

### APTS Audit Log
- **Log:** `/tmp/css-scan-20260426T174527Z.jsonl`
- **Tool runs recorded:** 13
- **Standard:** OWASP APTS § Auditability
