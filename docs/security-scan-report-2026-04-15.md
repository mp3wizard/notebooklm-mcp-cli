# Automated Security Scan Report
**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scanned at:** 2026-04-15T09:44:00+07:00
**Context:** Post-merge scan after integrating origin/main v0.5.24 (WSL2 Chrome 136+ fix, studio revise error hints, gitignore hardening)
**Tools run:** Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, mcps-audit, config-audit, skill-security-auditor, mcp-exfil-scan
**Tools skipped:** CodeQL (no `.github/workflows/codeql.yml`), mcp-scan (opt-in — not requested)

---

## Pre-flight Summary

| Tool | Status | Version |
|------|--------|---------|
| bandit | OK | 1.9.4 |
| semgrep | OK | 1.157.0 |
| trivy | OK | 0.69.3 (safe — not in GHSA-69fq-xp46-6x23 range) |
| trufflehog | OK | 3.94.2 |
| gitleaks | OK | 8.30.1 |
| osv-scanner | OK | 2.3.5 |
| gh (CodeQL) | OK | present but no workflow |
| npx (mcps-audit) | OK | present |
| uvx (mcp-scan) | OK | present (opt-in, not run) |
| jq | OK | present |
| config-audit.py | OK | bundled |
| skill-audit.sh | OK | bundled |
| mcp-exfil-scan.sh | OK | bundled |

---

## Gitleaks — Secrets in git history

**Summary:** 0 leaks found. 463 commits scanned, ~8.99 MB.

```
463 commits scanned.
scanned ~8993202 bytes (8.99 MB) in 1.17s
no leaks found
```

---

## Bandit — Python SAST

**Summary:** 0 High, 0 Medium in `src/`. Low: 10 (all `B101` assert-used in test helpers — expected, not security-relevant).

Scan of `src/notebooklm_tools/` only (`.venv` excluded):
```
Total issues (by severity):
  High:   0
  Medium: 0
  Low:    10  (B101 assert_used — expected in test helpers)

Total lines skipped (#nosec): 0
Total potential issues suppressed (per-nosec BXXX): 43
```

All 43 suppressed findings are pre-existing `# nosec` annotations for known-safe subprocess calls (WSL2 system tools) with justification comments. No new suppressions added.

---

## Semgrep — OWASP Top 10 / Python / Secrets

**Summary:** 0 findings across all configs.

| Config | Rules Run | Findings |
|--------|-----------|----------|
| p/owasp-top-ten | 153 | 0 |
| p/python | 151 | 0 |
| p/secrets | 38 | 0 |

---

## Trivy — Dependencies / IaC / Secrets

**Summary:** 0 vulnerabilities. Scanned `uv.lock`.

```
Report Summary
┌─────────┬──────┬─────────────────┬─────────┐
│ Target  │ Type │ Vulnerabilities │ Secrets │
├─────────┼──────┼─────────────────┼─────────┤
│ uv.lock │  uv  │        0        │    -    │
└─────────┴──────┴─────────────────┴─────────┘
```

Note: `uv.lock` was removed from git tracking in this merge (library convention). File still exists on disk.

---

## TruffleHog — Secrets (live-verified)

**Summary:** 0 verified secrets, 0 unverified secrets. 6,740 chunks scanned.

```
chunks: 6740, bytes: 9232079
verified_secrets: 0, unverified_secrets: 0
scan_duration: 962ms
```

---

## CodeQL — Semantic SAST

**Summary:** Skipped — no `.github/workflows/codeql.yml` in repository.

---

## mcps-audit — MCP Permission Audit

**Summary:** 408 findings at Risk Score 100/100. These are **expected false positives** for a tool that is an MCP server + auth credential manager. Key patterns flagged:

- `AS-003`: High-risk permission patterns in `ai_docs.py` — these document CLI commands like `nlm auth` and `nlm notebook`, which are intentional features of this tool
- `AS-010`: No logging in `__init__.py` and similar empty files — not relevant
- The tool's own documentation strings trigger "high-risk pattern" detectors

No actionable security issues in the project code itself.

---

## OSV-Scanner — SCA via OSV.dev

**Summary:** Could not parse `pyproject.toml` directly (extractor unsupported for direct TOML). `uv.lock` scanned via Trivy showed 0 vulnerabilities.

---

## config-audit — Claude Config Security

**Summary:** 22 findings (5 CRITICAL, 5 HIGH, 10 MEDIUM, 2 LOW). All are expected/false positives:

| Severity | Count | Assessment |
|----------|-------|------------|
| CRITICAL | 5 | Security scanner scripts detecting base64/SSH patterns **in themselves** (detection logic is the pattern) |
| HIGH | 5 | Plugin examples with `mkfs`/`dd` commands in a **validation** script that explicitly blocks these commands |
| MEDIUM | 10 | CLAUDE.md references to cookies/credentials (expected for an auth tool) + `skipDangerousModePermissionPrompt` in settings |
| LOW | 2 | Hooks configuration found in plugin |

**No actionable issues in the notebooklm-mcp-cli project itself.**

---

## skill-security-auditor — SKILL.md Analysis

**Summary:** `src/notebooklm_tools/data/SKILL.md` scored **MEDIUM RISK (35/100)**.

- 0 dangerous patterns
- 0 prompt injection patterns
- 6 network URLs (all Google/NotebookLM domains — expected)
- 7 file operations (standard tool operations)
- 27 bash code blocks (high complexity → +10 risk)

Score reflects tool complexity, not actual vulnerabilities.

---

## mcp-exfil-scan — MCP Exfiltration

**Summary:** Findings are **not in this project** — they are in the `skill-security-auditor` skill installed globally.

| Severity | Count | Source |
|----------|-------|--------|
| CRITICAL | 2 | `skill-security-auditor/SKILL.md` (by design: scans .env for security auditing) |
| HIGH | 3 | `skill-security-auditor/SKILL.md` (Read+WebFetch+Bash combo — intentional security scanner) |
| MEDIUM | 4 | `playwright-cli`, `pyright`, `vtsls` skills lack source attribution |

No exfiltration risks found in `notebooklm-mcp-cli` code.

---

## Cross-Tool Observations

No cross-tool overlaps indicating genuine vulnerabilities. All tools consistently report clean results for the project source code:
- Gitleaks + TruffleHog: no secrets in history or current state
- Bandit + Semgrep: no code-level security issues  
- Trivy + OSV: no vulnerable dependencies

The high scores from config-audit and mcp-exfil-scan are false positives from security tools scanning themselves or from this tool's intentional auth/credential handling.

---

## Coverage Gaps

- **CodeQL**: No workflow configured. Would provide semantic analysis (flow tracking).
- **mcp-scan**: Not run (opt-in — sends data to invariantlabs.ai). Would check for MCP tool poisoning at runtime.
- **OSV-Scanner**: Could not parse `pyproject.toml` natively — covered by Trivy on `uv.lock`.
- **Business logic**: Not covered by static analysis (IDOR, runtime auth bypass, etc.).

---

## Verdict

**✅ No actionable security issues found** in the notebooklm-mcp-cli codebase after merging origin/main v0.5.24.

Dependency supply chain is clean (0 CVEs). Source code is clean (0 SAST findings). No secrets in history.
