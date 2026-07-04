# Security Scan Report — 2026-07-04

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Trigger:** Automated post-merge scan after syncing upstream v0.8.2
**Scanned at:** 2026-07-04T02:39–02:42 UTC
**Git HEAD:** Post-merge (origin/main @ `4301456`)
**Standard:** OWASP APTS-aligned

## Commits Merged (v0.8.2)

| Hash | Description |
|------|-------------|
| `236a617` | chore: prepare v0.8.2 auth diagnostics |
| `a75e006` | fix: preserve google cookie domains (Fixes #249, @laofun) |
| `79ae39f` | chore: format cookie rotation test |
| `38ee7be` | fix: confirm auth redirects with rpc (Fixes #250, @laofun) |
| `9f1cc16` | docs: add v0.8.2 changelog entry and enforce changelog rule |
| `a8b53bd` | docs(changelog): remove unused Unreleased section |

## Scope Record

```
Scan target: /Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli
Git HEAD:    4301456 (post-merge, 634 commits)
Include:     src/, tests/, project root
Exclude:     .venv/ (third-party deps — not project source)
```

## Coverage Disclosure

| Tool | Status | Version | Finding Summary |
|------|--------|---------|-----------------|
| Gitleaks | OK | 8.30.1 | 0 secrets in 634 commits |
| Bandit | OK | 1.9.4 | 0 High, 0 Medium in src/ (10 Low — all expected patterns) |
| Semgrep OWASP | OK | latest | 0 findings in 99 files |
| Semgrep Python | OK | latest | 0 findings in 99 files |
| Semgrep Secrets | OK | latest | 0 findings in 107 files |
| Trivy | OK | 0.71.2 | 0 vulns in uv.lock (88 packages) |
| TruffleHog | OK | 3.95.6 | 0 verified/unverified secrets |
| OSV-Scanner | OK | 2.4.0 | No issues found |
| config-audit | OK | bundled | CRITICAL/HIGH all false positives (see below) |
| mcp-exfil-scan | OK | bundled | CLEAN (0/100) |
| skill-audit | OK | bundled | Score on project SKILL.md — findings are FPs by design |
| CodeQL | SKIPPED | — | No .github/workflows/codeql.yml in fork |
| mcps-audit | SKIPPED | — | No .skill files requiring mcps-audit |
| mcp-scan | OPT-IN | — | Not run (sends data to invariantlabs.ai) |
| skillspector | SKIPPED | — | No new AI-skill artifacts introduced in this merge |

## Tool Results

### Gitleaks
**Summary:** 0 secrets. 634 commits scanned, ~10.17 MB, 2.27s.

### Bandit
**Summary (src/ only):** 0 High, 0 Medium, 10 Low.

Low findings: all `B403` (subprocess import), `B404`/`B603` (subprocess call without `shell=True`), and `B110` (try/except/pass) patterns — standard Python patterns expected in a CLI tool that shells out for Chrome CDP. None are actionable.

### Semgrep
**Summary:** 0 findings across all three rulesets:
- `p/owasp-top-ten`: 0 findings, 99 files, 153 rules
- `p/python`: 0 findings, 99 files, 151 rules
- `p/secrets`: 0 findings, 107 files, 37 rules

Coverage note: `--max-target-bytes 300000` — no project source files >300 KB.

### Trivy
**Summary:** 0 vulnerabilities. uv.lock scanned (88 packages). No secrets flagged.

### TruffleHog
**Summary:** 0 verified secrets, 0 unverified secrets. 8,213 chunks, 10.49 MB scanned.

### OSV-Scanner
**Summary:** No issues found in uv.lock (88 packages).

### Config Audit
**Reported:** CRITICAL: 7, HIGH: 11, MEDIUM: 34, LOW: 7

**All CRITICAL and HIGH findings are false positives:**

| Finding | Verdict |
|---------|---------|
| 7× CRITICAL on security-scanner plugin scripts, caveman plugin install.sh/uninstall.sh | FP — scanner's own detection scripts trigger themselves; caveman curl fetches from GitHub releases (not exfiltration) |
| 7× HIGH on `~/.claude/settings.json` cc-beeper hooks | FP — cc-beeper is a local notification daemon at `localhost:${PORT}`; curl targets `http://localhost:...` only |
| 2× HIGH on plugin-dev validate-bash.sh examples | FP — educational example scripts demonstrating dangerous command patterns to block |
| 34× MEDIUM on broad hook matchers | INFO — expected normal plugin/hook operation across caveman, openai-codex, addy-agent-skills, claude-plugins-official, pordee |
| MEDIUM on CLAUDE.md credential/cookie references | FP — this project explicitly handles Google credentials by design (NotebookLM auth) |
| MEDIUM on `skipDangerousModePermissionPrompt: true` | LOW INFO — user-configured global setting |

### MCP Exfil Scan
**Verdict:** CLEAN (0/100). No tool description poisoning, outbound flow, exfil chains, encoded payloads, env var leaking, or source trust issues detected across 5 MCP configs and 10 skill files.

### Skill Audit (project SKILL.md)
**Score:** 75/100 — all findings are false positives by design:
- "Potential credential access" — SKILL.md documents Google auth cookie handling; expected for a credential-management tool
- "Silent action instruction" — pattern match on workflow-description text, not executable instruction bypass
- URLs (example.com, youtube.com) — documentation examples only

## Fixes Applied

**None required.** Zero vulnerabilities in project dependencies (Trivy + OSV-Scanner clean). Zero exploitable SAST findings in project source code (Semgrep, Bandit). No secrets in git history (Gitleaks + TruffleHog clean).

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| Very High | 0 | — |
| High | 0 in src/ | — |
| Medium | 0 in src/ | — |
| Low | 10 in src/ | All expected subprocess/try-except patterns in CLI code |
| Info | config-audit flags | All false positives (see above) |

## Tools Used

Gitleaks 8.30.1 · Bandit 1.9.4 · Semgrep (latest) · Trivy 0.71.2 · TruffleHog 3.95.6 · OSV-Scanner 2.4.0 · config-audit (bundled) · skill-audit (bundled) · mcp-exfil-scan (bundled)

**APTS Audit Log:** `/tmp/css-scan-20260704T023934Z.jsonl` · 4 measured tool runs
