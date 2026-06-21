# Security Scan Report — 2026-06-21

**Target:** `notebooklm-mcp-cli` (mp3wizard fork)
**Scanned at:** 2026-06-21T02:45Z
**Git HEAD:** a8cdcaa (post-merge v0.7.8)
**Trigger:** Daily upstream sync — v0.7.7 to v0.7.8 (6 commits merged)
**Standard:** OWASP APTS-aligned (Scope Enforcement, Auditability, Manipulation Resistance, Reporting)

## Upstream Changes Merged

| Version | Key Changes |
|---------|-------------|
| v0.7.8 (1b1f8a8) | Studio artifact source provenance via `source_ids`; actionable file upload errors; regional audio accent locale docs; skill capability audit; fix nested artifact source ID parsing |

### Commits in this merge
- `62e82cf` **feat(studio):** expose per-artifact `source_ids` in `studio_status` (PR #240, @tonhuu96)
- `8e1a98c` Merge pull request #240
- `bd955eb` **fix(studio):** parse nested artifact source IDs
- `3f03cf1` **docs:** clarify audio locales and file upload errors
- `a88ea4b` **refactor(sources):** simplify file error handling
- `1b1f8a8` **chore(release):** prepare v0.7.8

## Merge Notes

No merge conflicts. uv.lock had a local modification (security upgrades from prior session: authlib 1.7.2, cryptography 49.0.0) that conflicted with the upstream version bump. Stashed, merged cleanly, then re-applied security upgrades via `uv lock --upgrade-package` after scanning.

## Tool Coverage

| Tool | Version | Status | Findings in project source |
|------|---------|--------|---------------------------|
| Gitleaks | 8.30.1 | ✅ OK | 0 secrets (618 commits, 10 MB) |
| TruffleHog | 3.95.5 | ✅ OK | 0 verified, 0 unverified (8064 chunks) |
| Bandit | 1.9.4 | ✅ OK | 0 High; 74 Medium B108 in tests (false positives); 1 Medium B102 in test (false positive) |
| Semgrep OWASP | 1.166.0 | ✅ OK | 0 (102 Python files, 153 rules) |
| Semgrep Python | 1.166.0 | ✅ OK | 0 (102 Python files, 151 rules) |
| Semgrep Secrets | 1.166.0 | ✅ OK | 0 (159 files; 1 PDF skipped >300KB) |
| Trivy | 0.71.1 | ✅ OK | **20 before fix → 0 after fix** (uv.lock, 88 pkgs) |
| OSV-Scanner | 2.3.8 | ✅ OK | 0 issues (post-fix) |
| config-audit | bundled | ✅ OK | LOW only — hooks in user-level Claude Code config |
| skill-audit | bundled | ✅ OK | False positives only (documentation SKILL.md) |
| mcp-exfil-scan | bundled | ✅ OK | All findings in ~/.claude/skills/ (out of project scope) |
| CodeQL | — | SKIPPED | Remote GitHub Actions only |
| skillspector | — | N/A | OPT-IN |
| mcp-scan | — | N/A | OPT-IN (sends data to invariantlabs.ai) |

## Dependency Vulnerabilities Found and Fixed

Trivy detected **20 vulnerabilities** in uv.lock at the time of scan (post-merge, pre-fix).

### HIGH (4 unique packages, 6 CVEs)

| Package | Installed | Fixed | CVE/GHSA | Description |
|---------|-----------|-------|----------|-------------|
| cryptography | 46.0.7 | 48.0.1 | GHSA-537c-gmf6-5ccf | Vulnerable OpenSSL bundled in wheels |
| python-multipart | 0.0.26 | 0.0.27 | CVE-2026-42561 | Streaming multipart parser vulnerability |
| python-multipart | 0.0.26 | 0.0.30 | CVE-2026-53539 | Quadratic-time querystring parsing DoS |
| starlette | 1.0.0 | 1.1.0 | CVE-2026-48818 | SSRF and NTLM credential theft via UNC paths in StaticFiles |
| starlette | 1.0.0 | 1.3.1 | CVE-2026-54283 | form() limits silently ignored — DoS |

### MEDIUM (4 packages, 6 CVEs)

| Package | Installed | Fixed | CVE/GHSA | Description |
|---------|-----------|-------|----------|-------------|
| authlib | 1.6.10 | 1.6.11 | CVE-2026-41425 | CSRF in OAuth cache feature |
| authlib | 1.6.10 | 1.7.1 | CVE-2026-44681 | OAuth/OpenID vulnerability |
| idna | 3.11 | 3.15 | CVE-2026-45409 | IDNA parsing vulnerability |
| pydantic-settings | 2.13.1 | 2.14.2 | GHSA-4xgf-cpjx-pc3j | Symlink traversal outside secrets_dir |
| starlette | 1.0.0 | 1.0.1 | CVE-2026-48710 | Security restriction bypass via malformed HTTP Host header |
| starlette | 1.0.0 | 1.1.0 | CVE-2026-48817 | Information disclosure via non-standard HTTP methods |

### LOW (5 CVEs)

All resolved by the package upgrades applied above:
- python-multipart: CVE-2026-53537, CVE-2026-53538, CVE-2026-53540
- starlette: CVE-2026-54282
- pyjwt: CVE-2026-48524 (pyjwt was already at 2.13.0, fixed version — false positive from stale scan state)

### Fixes Applied (Phase 3c)

All performed via `uv lock --upgrade-package <pkg>` then `uv sync`:

| Package | Before | After | Resolves |
|---------|--------|-------|---------|
| cryptography | 46.0.7 | **49.0.0** | GHSA-537c-gmf6-5ccf |
| authlib | 1.6.10 | **1.7.2** | CVE-2026-41425, CVE-2026-44681 |
| joserfc | (new dep) | **1.7.1** | authlib 1.7.2 dependency |
| idna | 3.11 | **3.18** | CVE-2026-45409 |
| pydantic-settings | 2.13.1 | **2.14.2** | GHSA-4xgf-cpjx-pc3j |
| python-multipart | 0.0.26 | **0.0.32** | CVE-2026-42561, CVE-2026-53539, + 3 LOW |
| starlette | 1.0.0 | **1.3.1** | CVE-2026-48818, CVE-2026-54283, CVE-2026-48710, CVE-2026-48817, + LOW |

**Trivy post-fix verification: 0 vulnerabilities** ✅  
**OSV-Scanner post-fix: 0 issues** ✅

Note: All vulnerable packages are **transitive dependencies via `fastmcp`** — not direct project dependencies. Upgrades applied directly to `uv.lock` via `--upgrade-package`.

## Bandit Analysis

- **Source code (src/):** 0 Medium or High findings
- **Test code (tests/):** 74 Medium B108 (hardcoded `/tmp/` path in test fixtures — standard pytest pattern, not a runtime concern); 1 Medium B102 exec in `test_auth_service.py` (testing exec behavior in unit test)
- **All 1582 Low findings** are `assert_used` in tests (expected for pytest)
- **Accepted false positives:** `# nosec` suppressions in `utils/wsl.py` (B603/B607 for Windows subprocess calls with known-safe arguments)

## Semgrep Analysis

OWASP Top 10, Python ruleset, and Secrets ruleset all returned 0 findings across 102 Python files and 159 total files (688 combined rules). Clean.

## Secret Scanning

- **Gitleaks:** 0 leaks across 618 commits (10 MB)
- **TruffleHog:** 0 verified / 0 unverified secrets (8064 chunks, git history mode)

## APTS Audit Log

- **Log:** `/tmp/css-scan-20260621T023852Z.jsonl`
- **Tool runs recorded:** 10 (measured: 10, asserted: 0)
- **Standard:** OWASP APTS § Auditability

## Overall Risk Posture

**Clean** ✅ — 20 dependency vulnerabilities fixed; project source has 0 SAST or secret findings. Post-fix Trivy and OSV-Scanner both report 0 issues.
