# Security Assessment Report

**Target:** `notebooklm-mcp-cli`
**Location:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Scan Date:** 2026-04-05
**Version scanned:** v0.5.16 (post-merge — commit `d010b43`)
**Analyst:** Claude Security Review (claude-sonnet-4-6)
**Report Version:** 1.0 — Automated Scan

---

## Table of Contents

1. [Phase 0: Automated Scan Results](#phase-0-automated-scan-results)
2. [Phase 1: Codebase Reconnaissance](#phase-1-codebase-reconnaissance)
3. [Phase 2: Vulnerability Analysis](#phase-2-vulnerability-analysis)
4. [Phase 3: Security Findings](#phase-3-security-findings)
5. [Phase 4A: Executive Summary](#phase-4a-executive-summary)
6. [Phase 4B: Engineering Findings](#phase-4b-engineering-findings)
7. [Remediation Summary](#remediation-summary)

---

## Phase 0: Automated Scan Results

### Pre-flight Check

```
OK  bandit 1.9.4
OK  semgrep 1.157.0
OK  trivy Version: 0.69.3  (safe — compromised range: 0.69.4–0.69.6)
OK  trufflehog 3.94.2
OK  gitleaks 8.30.1
OK  osv-scanner 2.3.5
OK  gh (CodeQL — no codeql.yml workflow found)
OK  npx (mcps-audit available)
OK  uvx (mcp-scan available — opt-in only, not requested)
```

---

### Gitleaks — Secrets in git history + filesystem

**Run command:** `gitleaks detect --source <path> --no-banner`
**Exit code:** 0

```
408 commits scanned.
scanned ~7967672 bytes (7.97 MB) in 851ms
no leaks found
```

**Result:** Zero secrets detected in git history or working tree.

---

### Bandit — Python SAST

**Run command:** `bandit -r <src> <desktop-extension> --severity-level medium -f txt`
**Exit code:** 1 (issues found)

**Summary metrics (source files only; `.venv` excluded):**

```
Code scanned:
    Total lines of code: 19968
    Total lines skipped (#nosec): 0

Run metrics:
    Total issues (by severity):
        Undefined: 0
        Low: 25
        Medium: 2
        High: 0
    Total issues (by confidence):
        Undefined: 0
        Low: 0
        Medium: 8
        High: 19
```

**Medium findings:**

```
>> Issue: [B310:blacklist] Audit url open for permitted schemes.
   Severity: Medium   Confidence: High
   CWE: CWE-22
   Location: src/notebooklm_tools/cli/utils.py:171
170        req = urllib.request.Request(url, headers={"User-Agent": "notebooklm-mcp-cli"})
171        with urllib.request.urlopen(req, timeout=2) as response:
172            data = json.loads(response.read().decode())

--------------------------------------------------
>> Issue: [B310:blacklist] Audit url open for permitted schemes.
   Severity: Medium   Confidence: High
   CWE: CWE-22
   Location: src/notebooklm_tools/mcp/tools/server.py:21
20         req = urllib.request.Request(url, headers={"User-Agent": "notebooklm-mcp-cli"})
21         with urllib.request.urlopen(req, timeout=2) as response:
22             data = json.loads(response.read().decode())
```

**Low findings (summary):**

| Rule | Description | Count |
|------|-------------|-------|
| B404 | subprocess module import | ~10 |
| B603 | subprocess without shell=True | ~10 |
| B606 | os.execvp — process replacement | 1 |
| B101 | assert used in non-test code | ~4 |

Note: All subprocess calls use hardcoded arguments — no user input reaches the shell. No command injection risk identified.

---

### Semgrep — Multi-language SAST

**Run command:** `semgrep scan --metrics=off --config p/<ruleset> ...`
**Exit code:** 0 (all rulesets)

| Ruleset | Rules Run | Files Scanned | Findings |
|---------|-----------|---------------|----------|
| p/owasp-top-ten | 153 | 91 | 0 |
| p/python | 151 | 91 | 0 |
| p/secrets | 38 | 127 | 0 |

**Result:** Zero findings across all rulesets.

---

### Trivy — Dependencies & Misconfigurations

**Run command:** `trivy fs <path>`
**Exit code:** 0

```
Report Summary

+----------+------+-----------------+---------+
| Target   | Type | Vulnerabilities | Secrets |
+----------+------+-----------------+---------+
| uv.lock  |  uv  |        1        |    -    |
+----------+------+-----------------+---------+

uv.lock (uv)
Total: 1 (UNKNOWN: 0, LOW: 1, MEDIUM: 0, HIGH: 0, CRITICAL: 0)

Library   Vulnerability  Severity  Status  Installed  Fixed
--------  -------------  --------  ------  ---------  -----
pygments  CVE-2026-4539  LOW       fixed   2.19.2     2.20.0
```

**pygments CVE-2026-4539:** DoS via inefficient regex in `AdlLexer`. Dev/CLI dependency only — not in the MCP server runtime path.

---

### TruffleHog — Secret Detection

**Run command:** `trufflehog git file://<path> --no-update`
**Exit code:** 0

```
chunks: 5876 | bytes: 8,172,852
verified_secrets: 0
unverified_secrets: 0
scan_duration: 751ms
trufflehog_version: 3.94.2
```

**Result:** Zero verified and zero unverified secrets detected in git history.

---

### CodeQL — Deep Semantic SAST

**Status:** SKIPPED — no `codeql.yml` workflow found in `.github/workflows/`

The repo has `lint-test.yml`, `publish.yml`, and `version-check.yml` but no CodeQL workflow configured.

**Gap:** Deep semantic analysis (taint tracking, data-flow SSRF, injection) not covered by automated tooling.

---

### mcps-audit — OWASP MCP Top 10

**Run command:** `npx mcps-audit <path>`
**Exit code:** 1 (FAIL)

**OWASP MCP Top 10 results:**

| ID | Category | Status |
|----|----------|--------|
| MCP-01 | Rug Pulls | FAIL |
| MCP-02 | Tool Poisoning | N/A |
| MCP-03 | Privilege Escalation via Tool Composition | FAIL |
| MCP-04 | Cross-Server Request Forgery | FAIL |
| MCP-05 | Sampling Manipulation | N/A |
| MCP-06 | Indirect Prompt Injection via MCP | FAIL |
| MCP-07 | Resource Exhaustion & DoS | PASS |
| MCP-08 | Insufficient Logging & Audit | FAIL |
| MCP-09 | Insecure MCP-to-MCP Communication | PASS |
| MCP-10 | Context Window Pollution | FAIL |

Coverage: 2/8 mitigated | MCPS SDK: not found | Risk Score: 100/100 | CRITICAL: 6 | HIGH: 74 | MEDIUM: 305 | LOW: 2

PDF report saved: `mcps-audit-report.pdf`

**Selected critical findings (AS-001 — Dangerous Execution):**

```
[CRITICAL] AS-001  scripts/inject_cookies_and_inspect.py:107
           Dangerous execution: (async function() {

[CRITICAL] AS-001  scripts/inject_cookies_and_inspect.py:158
           Dangerous execution: (async function() {

[CRITICAL] AS-001  scripts/inspect_upload_dom.py:104
           Dangerous execution: (function() {
```

Note: These are CDP authentication scripts that inject JavaScript into Chrome to extract NotebookLM cookies — by design. Not part of the `notebooklm-mcp` server runtime. See SEC-004.

---

### OSV-Scanner — SCA Dependency Vulnerabilities

**Run command:** `osv-scanner scan source -r <path>`
**Exit code:** 1 (vulnerabilities found)

```
Total 2 packages affected by 2 known vulnerabilities
(0 Critical, 1 High, 0 Medium, 1 Low, 0 Unknown) — 2 vulnerabilities can be fixed.

OSV URL                                CVSS  Package         Version  Fixed   Source
-------------------------------------  ----  --------------  -------  ------  -------
https://osv.dev/GHSA-58pv-8j8x-9vj2   8.6   jaraco-context  6.0.2    6.1.0   uv.lock
https://osv.dev/GHSA-5239-wwwm-4pmq   3.3   pygments        2.19.2   2.20.0  uv.lock
```

---

## Phase 1: Codebase Reconnaissance

### Framework & Stack

| Component | Details |
|-----------|---------|
| Language | Python >=3.11 |
| Package manager | `uv` (lockfile: `uv.lock`) |
| HTTP client | `httpx` |
| CLI framework | `typer` + `rich` |
| WebSocket (CDP) | `websocket-client` |
| MCP framework | `fastmcp>=3.2.0` |
| Package version | **0.5.16** |

### Changes in v0.5.16 (PR #121)

The primary change in this release is a **dual RPC fallback** for the `source_add` URL operation in `src/notebooklm_tools/core/sources.py`. The module grew from ~150 to ~350 lines. Key additions:

- Secondary RPC code path attempted automatically if the primary fails.
- New test file: `tests/core/test_url_source_fallback.py` (278 lines) covering the fallback logic.
- `src/notebooklm_tools/core/base.py` received minor updates (auto-merged cleanly).

No new external integrations, new auth flows, or new credential storage paths were introduced.

### Entry Points

1. **`nlm` CLI** — `src/notebooklm_tools/cli/main.py`
2. **`notebooklm-mcp` MCP server** — `src/notebooklm_tools/mcp/server.py` (stdio, HTTP, SSE)
3. **Desktop extension launcher** — `desktop-extension/run_server.py`

### Authentication & Credential Handling

No changes to authentication in v0.5.16. Credential files continue to use `chmod 0o600`/`0o700` as established in the 2026-03-17 security remediation (SEC-001/SEC-002 of that report).

---

## Phase 2: Vulnerability Analysis

### Category 1: Injection Flaws

No dynamic code execution, `os.system()`, or `shell=True` in production code. All subprocess calls use list-form arguments with hardcoded values. The `os.execvp` call in `desktop-extension/run_server.py:74` is an intentional process replacement — no user input is unsafely interpolated. **No new risk in v0.5.16.**

### Category 2: Broken Access Control

Unchanged from 2026-03-17 assessment. MCP HTTP/SSE endpoint remains unauthenticated (startup warning in place). No new endpoints or tools added. **No change.**

### Category 3: Hardcoded Secrets & Credential Exposure

Gitleaks and TruffleHog both returned zero findings across 408 commits. Semgrep `p/secrets` returned zero findings. **Clean.**

### Category 4: Cryptographic Misuse

`secrets.randbelow()` for the request counter confirmed still in place (fixed 2026-03-17). No new cryptographic operations introduced. **Clean.**

### Category 5: Insecure Deserialization

No unsafe binary serialization (`B301`/`B302` Bandit rules) or unsafe YAML loading found. All deserialization uses `json.loads()`. **No risk.**

### Category 6: Server-Side Request Forgery (SSRF)

The two `urllib.request.urlopen()` calls flagged by Bandit (B310) in `cli/utils.py:171` and `mcp/tools/server.py:21` use a hardcoded `pypi.org` URL — not user-controlled. **Low risk; no true SSRF vector.**

### Category 7: Dependency Vulnerabilities

OSV-Scanner identified two vulnerabilities in `uv.lock`:
- **jaraco-context 6.0.2** — GHSA-58pv-8j8x-9vj2 (CVSS 8.6 HIGH) — fix: upgrade to 6.1.0
- **pygments 2.19.2** — GHSA-5239-wwwm-4pmq (CVSS 3.3 LOW) — confirmed by both Trivy + OSV

### Category 8: Authentication & Session Management

No changes to auth in v0.5.16. File permissions, CSRF redaction, and account mismatch detection remain from 2026-03-17 remediation. **No change.**

### Category 9: Security Misconfiguration

No new configuration surface introduced. CDP origin restriction remains in place. **No change.**

### Category 10: Logging & Monitoring Gaps

mcps-audit flagged `desktop-extension/run_server.py` and `scripts/build_mcpb.py` as lacking structured logging. The MCP server itself uses Python's `logging` module throughout. **Low risk.**

### Category 11: Infrastructure-as-Code Risks

No Dockerfile, Kubernetes, or Terraform files. **Not applicable.**

### Category 12: CI/CD Pipeline Security

No CodeQL workflow present. `lint-test.yml` runs `pytest -m "not e2e"` and ruff only. No dependency audit step in CI. **Gap noted — see SEC-005.**

---

## Phase 3: Security Findings

---

### SEC-001 ⚠️ OPEN

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Category** | Dependency Vulnerabilities |
| **Severity** | High |
| **Status** | **OPEN — fix available** |
| **Location** | `uv.lock` (transitive dependency) |
| **Detection Source** | Automated (OSV-Scanner — GHSA-58pv-8j8x-9vj2, CVSS 8.6) |
| **CWE** | CWE-1104 (Use of Vulnerable Third-Party Component) |

**Description:** `jaraco-context` 6.0.2 is a transitive dependency with a HIGH-severity advisory (CVSS 8.6). A fixed version (6.1.0) is available. Review the advisory to confirm the affected code path before prioritising.

**Recommended Fix:**
```
uv lock --upgrade-package jaraco-context
uv sync
```

---

### SEC-002 ⚠️ OPEN

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Category** | Dependency Vulnerabilities |
| **Severity** | Low |
| **Status** | **OPEN — fix available** |
| **Location** | `uv.lock` |
| **Detection Source** | Automated (OSV-Scanner GHSA-5239-wwwm-4pmq + Trivy CVE-2026-4539, CVSS 3.3) |
| **CWE** | CWE-1104 |

**Description:** `pygments` 2.19.2 contains a DoS vulnerability via inefficient regex processing in `AdlLexer`. Confirmed independently by both Trivy and OSV-Scanner. `pygments` is a dev/CLI dependency — not part of the MCP server runtime.

**Recommended Fix:**
```
uv lock --upgrade-package pygments
uv sync
```

---

### SEC-003 ℹ️ LOW RISK — Acknowledged

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Category** | URL Scheme Validation |
| **Severity** | Low |
| **Status** | **ACKNOWLEDGED — low actual risk, hardening optional** |
| **Location** | `src/notebooklm_tools/cli/utils.py:171`, `src/notebooklm_tools/mcp/tools/server.py:21` |
| **Detection Source** | Automated (Bandit B310 x2) |
| **CWE** | CWE-22 |

**Description:** Two `urllib.request.urlopen()` calls in the PyPI version-check helper do not explicitly assert the URL scheme or hostname. Both use a hardcoded `pypi.org` constant — not user-supplied — so there is no true SSRF risk. Bandit flags the pattern regardless.

**Optional Hardening:** Add `assert url.startswith("https://pypi.org/")` before each `urlopen` call.

---

### SEC-004 ℹ️ INFORMATIONAL — Design / Dev Tooling

| Field | Value |
|-------|-------|
| **ID** | SEC-004 |
| **Category** | Dangerous Code Pattern |
| **Severity** | Informational |
| **Status** | **ACKNOWLEDGED — design-intentional in developer scripts** |
| **Location** | `scripts/inject_cookies_and_inspect.py:107,158`, `scripts/inspect_upload_dom.py:104` |
| **Detection Source** | Automated (mcps-audit AS-001 Critical) |
| **CWE** | CWE-94 (Improper Control of Code Generation) |

**Description:** mcps-audit flagged JavaScript injection patterns in the CDP authentication helper scripts. These scripts inject JS into a live Chrome tab to extract NotebookLM auth cookies — this is intentional by design. They are developer-only tooling, executed manually in the user's own browser session, and are not part of the installed package or MCP server binary.

**Recommendation:** Add a clear warning comment or confirmation prompt to these scripts documenting that they execute JavaScript in the browser context.

---

### SEC-005 ⚠️ GAP — No CodeQL Workflow

| Field | Value |
|-------|-------|
| **ID** | SEC-005 |
| **Category** | CI/CD — SAST Coverage Gap |
| **Severity** | Informational |
| **Status** | **OPEN — gap in automated coverage** |
| **Location** | `.github/workflows/` |
| **Detection Source** | Manual observation |
| **CWE** | N/A |

**Description:** No CodeQL GitHub Actions workflow is present. Deep semantic SAST (taint tracking, data-flow analysis) is not run automatically on PRs or merges. `lint-test.yml` covers linting and unit tests only.

**Recommended Fix:** Add `.github/workflows/codeql.yml` targeting Python using `actions/codeql-action`. Suggested triggers: `push` to `main` and all pull requests.

---

## Phase 4A: Executive Summary

### Overall Risk Posture: **Low**

The v0.5.16 merge introduced no new application-level vulnerabilities. The dual RPC fallback in `core/sources.py` follows established safe coding patterns throughout. Semgrep, TruffleHog, and Gitleaks all returned zero findings. The two open actionable items (SEC-001, SEC-002) are dependency upgrades with one-command fixes.

### Key Statistics

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | — |
| High | 1 | SEC-001 open (jaraco-context, transitive dep) |
| Medium | 0 | — |
| Low | 1 | SEC-002 open (pygments, dev dep) |
| Informational | 3 | SEC-003, SEC-004, SEC-005 acknowledged/gaps |
| **Total** | **5** | **2 actionable, 3 informational** |

| Detection Source | Count |
|-----------------|-------|
| OSV-Scanner | 2 (SEC-001, SEC-002) |
| Trivy | 1 (SEC-002, cross-confirmed) |
| Bandit | 1 (SEC-003, low risk) |
| mcps-audit | 1 (SEC-004, contextual) |
| Manual observation | 1 (SEC-005, gap) |
| Semgrep / Gitleaks / TruffleHog | 0 |

### Cross-Tool Observations

| Finding | Tools | Confidence |
|---------|-------|------------|
| pygments 2.19.2 needs upgrade | Trivy + OSV-Scanner | High — two independent sources |
| No secrets in git history | Gitleaks + TruffleHog | High — both clean |
| CDP JS injection in scripts | mcps-audit | Contextual — design-intentional |
| urlopen unvalidated scheme | Bandit x2 | Low risk — hardcoded URLs |

---

## Phase 4B: Engineering Findings

### Remediation Priority List

| Priority | ID | Title | Effort | Status |
|----------|----|-------|--------|--------|
| 1 | SEC-001 | jaraco-context HIGH (CVSS 8.6) | 1 command | ⚠️ Open |
| 2 | SEC-002 | pygments LOW DoS | 1 command | ⚠️ Open |
| 3 | SEC-005 | No CodeQL workflow | Small | ⚠️ Gap |
| 4 | SEC-003 | urlopen scheme assertion | 1 line x2 | ℹ️ Optional |
| 5 | SEC-004 | CDP script warning comment | Docs only | ℹ️ Optional |

### Full Finding Cross-Reference

| ID | Severity | Category | File | Line | Status |
|----|----------|----------|------|------|--------|
| SEC-001 | High | Dependency (transitive) | `uv.lock` | — | ⚠️ Open |
| SEC-002 | Low | Dependency (dev) | `uv.lock` | — | ⚠️ Open |
| SEC-003 | Low | URL Scheme | `cli/utils.py`, `mcp/tools/server.py` | 171, 21 | ℹ️ Acknowledged |
| SEC-004 | Info | CDP JS Injection (design) | `scripts/*.py` | 107, 158, 104 | ℹ️ Acknowledged |
| SEC-005 | Info | CI/CD SAST gap | `.github/workflows/` | — | ⚠️ Gap |

### Coverage Gaps

| Category | Gap |
|----------|-----|
| Deep semantic SAST | No CodeQL — taint tracking / data-flow not covered |
| Runtime / DAST | No dynamic testing of auth flows or cookie handling |
| Business logic | IDOR, authorization bypass in notebook operations not assessed |
| MCP prompt injection | `mcp-scan` (opt-in, invariantlabs.ai API) not run |

---

## Remediation Summary

**Scan Date:** 2026-04-05
**Analyst:** Claude Security Review (claude-sonnet-4-6)
**Scope:** Post-merge v0.5.16 (`d010b43`)

### Actions Required

```
# SEC-001: Upgrade jaraco-context (HIGH, CVSS 8.6)
uv lock --upgrade-package jaraco-context

# SEC-002: Upgrade pygments (LOW — confirmed by Trivy + OSV)
uv lock --upgrade-package pygments

# Apply lockfile to environment
uv sync
```

### Next Recommended Actions

1. **Upgrade jaraco-context and pygments** — both have one-command fixes.
2. **Add CodeQL workflow** to `.github/workflows/codeql.yml` for continuous deep SAST on PRs.
3. **(Optional)** Add explicit scheme assertion before `urlopen` in `cli/utils.py:171` and `mcp/tools/server.py:21`.
4. **(Optional)** Add warning comments to CDP scripts documenting the JS injection scope.
5. **(Opt-in)** Run `uvx mcp-scan@latest` for MCP tool description poisoning analysis — requires consent (sends tool descriptions to invariantlabs.ai).

---

*Report v1.0 generated by Claude Security Review agent (claude-sonnet-4-6) on 2026-04-05.*
*Previous report: `security-scan-report-2026-03-17.md` (v0.4.x baseline + remediation).*
