# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-04-16T09:42:00+07:00
**Context:** Post-merge scan after integrating origin/main v0.5.25 (audio CDN fix, CDP proxy bypass, Windows UTF-8 fix)
**Tools run:** Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
**Tools skipped:** CodeQL (no `.github/workflows/codeql.yml`), mcp-scan (opt-in — not requested)

---

## Pre-flight Summary

| Tool | Status | Version |
|------|--------|---------|
| gitleaks | OK | 8.30.1 |
| bandit | OK | 1.9.4 |
| semgrep | OK | 1.157.0 (pipx — safe build) |
| trivy | OK | 0.69.3 (safe — not in GHSA-69fq-xp46-6x23 range) |
| trufflehog | OK | 3.94.2 |
| osv-scanner | OK | 2.3.5 |
| gh (CodeQL) | SKIPPED | No codeql.yml workflow |
| npx (mcps-audit) | N/A | No MCP JSON files in project root |
| uvx (mcp-scan) | OPT-IN | Not requested |
| jq | OK | present |
| config-audit.py | OK | bundled |
| skill-audit.sh | OK | bundled |
| mcp-exfil-scan.sh | OK | bundled |

---

## Gitleaks — Secrets in git history

**Summary:** 0 findings. 474 commits scanned, ~9 MB.

```
474 commits scanned.
scanned ~9011339 bytes (9.01 MB) in 1.16s
no leaks found
```

---

## Bandit — Python SAST

**Summary:** 0 findings in project `src/` at Medium severity or above.

**Project source findings (src/ only — all Low):**

| File | Issue | Severity | Assessment |
|------|-------|----------|------------|
| `core/conversation.py:247,250` | B101: assert used | Low | Type-narrowing assertions — intentional |
| `services/studio.py:322` | B101: assert used | Low | Post-validation assertion — intentional |
| `services/studio.py:622` | B110: try/except/pass | Low | Optional mind-map fetch — intentional |
| `utils/wsl.py:220` | B607/B603: subprocess partial path | Low | Fixed system call to `powershell.exe` |
| `utils/wsl.py:231` | B607/B603: subprocess partial path | Low | Fixed system call to `wslpath` |
| `utils/wsl.py:240` | B607/B603: subprocess partial path | Low | Fixed system call to `netsh` |

All `.venv/` findings excluded (third-party packages, not project code).
All `wsl.py` subprocess calls use fixed system executable names with no user-controlled input.

---

## Semgrep — OWASP Top 10 + Python + Secrets

**Summary:** 0 findings across all 3 rulesets.

```
OWASP:   0 findings (153 rules, 94 files)
Python:  0 findings (151 rules, 94 files)
Secrets: 0 findings (38 rules, 128 files)
```

---

## Trivy — Dependencies & Secrets

**Summary:** 0 vulnerabilities. 88 packages in uv.lock scanned.

```
┌─────────┬──────┬─────────────────┬─────────┐
│ Target  │ Type │ Vulnerabilities │ Secrets │
├─────────┼──────┼─────────────────┼─────────┤
│ uv.lock │  uv  │        0        │    -    │
└─────────┴──────┴─────────────────┴─────────┘
```

---

## TruffleHog — Secrets with live verification

**Summary:** 0 verified secrets, 0 unverified secrets.

```
chunks: 6778, bytes: 9251527
verified_secrets: 0, unverified_secrets: 0
scan_duration: 1.677s
```

---

## OSV-Scanner — SCA via OSV.dev

**Summary:** No issues found. 88 packages in uv.lock checked.

```
Scanned uv.lock file and found 88 packages
No issues found
```

---

## config-audit — Claude Config Security

**Summary:** 22 findings — all false positives. No actionable issues in project source.

| Severity | Count | Finding | Assessment |
|----------|-------|---------|------------|
| CRITICAL | 5 | Security scanner scripts contain base64/ncat/SSH references | FP — scanner tools checking *for* these patterns |
| HIGH | 4 | plugin-dev validate-bash.sh `mkfs`/`dd` patterns | FP — example hook showing patterns to *block* |
| HIGH | 1 | skill:optimize netcat mention | FP — documentation reference |
| MEDIUM | 1 | `skipDangerousModePermissionPrompt: true` | Known — intentional automation config |
| MEDIUM | 6 | CLAUDE.md references cookies/credentials | FP — authentication documentation for this tool |
| LOW | 2 | Hooks configuration found | Expected — user-configured hooks |

---

## Skill Audit

**Summary:** 2 skill files audited — no security issues.

| File | Score | Verdict |
|------|-------|---------|
| `notebooklm-cli.skill` | 0/100 | LOW RISK — no dangerous patterns |
| `src/notebooklm_tools/data/SKILL.md` | 35/100 | MEDIUM RISK — example URLs and bash blocks in documentation only |

---

## MCP Exfil Scan

**Summary:** 9 findings — all false positives from security tooling, 0 issues in project source.

| Severity | Finding | Assessment |
|----------|---------|------------|
| CRITICAL ×2 | `extract/SKILL.md`, `security-audit/SKILL.md` mention exfiltration patterns | FP — scanners checking for exfil |
| HIGH ×3 | `skill-security-auditor` has Read+WebFetch+Bash tools | FP — legitimate security auditor design |
| MEDIUM ×4 | Skills with no source attribution | FP — first-party bundled skills |

---

## Cross-Tool Observations

- **No cross-tool overlaps on real issues.** All tools agreed: project source code is clean.
- Gitleaks + TruffleHog both confirm **zero secrets** in git history or current files.
- Trivy + OSV-Scanner both confirm **zero vulnerable dependencies** (88 packages).
- Semgrep OWASP + Bandit both confirm **zero medium/high SAST issues** in `src/`.
- config-audit and mcp-exfil-scan high/critical findings trace back to security scanner skill scripts (meta false positives).

## Security Fixes Applied This Cycle

None required — all 88 dependencies clean, no CVEs found.

## Coverage Gaps

- Business logic, IDOR, runtime behavior not covered by static analysis.
- mcp-scan (invariantlabs.ai) not run — opt-in required.
- CodeQL not configured for this repo.

---

**Overall verdict: CLEAN — no action required.**
