# Security Scan Report — 2026-06-05

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-06-05T00:00Z
**Git HEAD:** 31e3782 (post-merge v0.7.0)
**Trigger:** Daily upstream sync — v0.6.15 → v0.7.0 (53 commits merged)
**Standard:** OWASP APTS-aligned (Scope Enforcement · Auditability · Manipulation Resistance · Reporting)

## Upstream Changes Merged

| Version | Key Changes |
|---------|-------------|
| v0.7.0 | Studio fast-track 2-step pipeline; cinematic video artifact type; short answer fix (type=1 chunks no longer dropped); audio download retry propagation fix; `format_item` dict handling for `--json`; HTTP 401/403 → "stale" not "unverified" in MCP server; new `docs/GETTING_STARTED.md`; 8 new contributors added to credits |
| v0.6.16 | Source polling improvements; studio status reliability |

## Tool Coverage

| Tool | Version | Status | Findings in project source |
|------|---------|--------|---------------------------|
| Gitleaks | 8.30.1 | OK | 0 |
| Bandit | 1.9.4 | OK | 5 Low (all in project source, accepted) |
| Semgrep OWASP | current | OK | 0 |
| Semgrep Python | current | OK | 0 |
| Semgrep Secrets | current | OK | 0 |
| Trivy | 0.69.3 | OK | 0 |
| TruffleHog | 3.94.2 | OK | 0 verified, 0 unverified |
| OSV-Scanner | 2.3.5 | OK | **1 fixed** (pyjwt — 4 CVEs) |
| mcps-audit | 1.0.0 (PDF) | OK | 480 findings (all pre-existing, architectural — see analysis) |
| security-audit | bundled | OK | 43 findings (all false positives or out-of-scope) |
| skill-auditor | bundled | OK | notebooklm-cli.skill: 0/100 LOW RISK |
| mcp-exfil-scan | bundled | OK | 11 findings (all in user global skills, out of project scope) |
| CodeQL | — | SKIPPED | No .github/workflows/codeql.yml |
| mcp-scan | — | OPT-IN | Not run |

## Vulnerability Summary

| Severity | Count | Status |
|----------|-------|--------|
| Very High | 0 | — |
| High | 1 (pyjwt) | **Fixed** |
| Medium | 0 | Clean |
| Low | 5 (Bandit) | Accepted, not fixed |
| Info | — | — |

## Dependency Scan (uv.lock)

**Trivy:** 0 vulnerabilities
**OSV-Scanner:** **4 CVEs in pyjwt 2.12.1** — PYSEC-2026-175, PYSEC-2026-176 (CVSS 4.9), PYSEC-2026-177, PYSEC-2026-178 / PYSEC-2026-179 (CVSS 7.4)

### pyjwt Fix Applied

```
pyproject.toml: "pyjwt>=2.12.0"  →  "pyjwt>=2.13.0"
uv.lock: pyjwt 2.12.1 → 2.13.0 (via uv lock --upgrade-package pyjwt && uv sync)
```

All 4 CVEs resolved. pyjwt 2.13.0 is the safe baseline — any fresh install from `pyproject.toml` will pull the patched version.

## Key Findings Analysis

### Bandit Low Severity (5 findings — accepted)

All in `src/notebooklm_tools/utils/cdp.py`:
- **B603** — `subprocess.Popen` with controlled args (Chrome CDP launch, not user input)
- **B607** — `start_new_session=True` process group (intentional for Chrome lifecycle management)
- **B110** — `try/except/pass` in cleanup paths (intentional best-effort teardown)

These are the same 5 accepted findings from the v0.6.13 and v0.6.15 scans. No new Bandit findings introduced by v0.7.0.

### mcps-audit PDF (480 findings, 100/100 risk score)

Pre-existing AgentSign audit report (dated 2026-06-02, 140 pages). All 480 findings are architectural patterns present before and after the v0.7.0 merge:
- `AS-001` "Dangerous execution" — `scripts/inject_cookies_and_inspect.py` (CDP development script, not production MCP)
- `AS-010` "No logging" — dev/utility scripts
- Every delete command flagged (`notebook_delete`, `source_delete`, `studio_delete`, `note_delete`) — systemic, by design
- `urllib.parse` usage flagged as "data exfiltration" — false positive (standard URL construction)
- Test fixture values (`csrf_token="test_token"`) flagged as "hardcoded credentials" — false positive

No findings specific to the v0.7.0 merge (studio fast-track, cinematic video, short answer fix).

### Secrets Scan (Gitleaks + TruffleHog)

**0 secrets** in git history or filesystem. Scanned 567+ commits (~9.5 MB repo). No verified or unverified secrets detected.

### SAST (Semgrep OWASP + Python + Secrets)

**0 findings** across all three rule sets. v0.7.0 changes (conversation.py type=1 chunk fix, download.py retry propagation, formatters.py dict handling) introduce no injection, deserialization, or path traversal patterns.

## Fixes Applied

| Package | Before | After | CVEs Fixed |
|---------|--------|-------|------------|
| pyjwt | 2.12.1 | 2.13.0 | PYSEC-2026-175/176/177/178/179 (max CVSS 7.4) |

## Overall Risk Posture

**CLEAN** ✅ (after pyjwt fix)

The v0.7.0 merge introduces no new security surface:
- Studio fast-track pipeline: no new external calls, no new auth paths
- Short answer fix (`conversation.py`): type-narrowing change only
- Audio download retry (`download.py`): error propagation only, no new network calls
- CLI `format_item` fix (`formatters.py`): output formatting only, no data access changes
- MCP auth status mapping: tightens error semantics (fewer false-success responses)

APTS Audit Log: `/tmp/css-scan-20260605.jsonl`
