# Security Scan Report — 2026-05-14 (post-merge v0.6.9)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD (post-merge):** `0056da9` (merge of `origin/main` @ `f743ade`)
**Trigger:** Daily upstream sync — merged 4 commits from `origin/main` (v0.6.8 → v0.6.9)

## Upstream changes merged

| Commit | Type | Summary |
|--------|------|---------|
| `6043538` | Feature | support `.epub` file uploads as notebook sources (PR #191, @mateogon) |
| `8a4c86c` | Merge | PR #191 |
| `9e70002` | Release | v0.6.9 — Hermes Agent skill install, Windows tool-detection / permission / encoding fixes, studio-status mind maps, shared `is_tool_on_system()` helper, typed `ToolConfig` |
| `f743ade` | Docs | credit @mateogon for EPUB upload support |

## Tools run

| Tool | Version | Result |
|------|---------|--------|
| Gitleaks | 8.30.1 | 0 leaks (530 commits, 9.29 MB) |
| Bandit | 1.9.4 | 3 Low (try/except/pass; 55 `# nosec` skipped); 22,782 LOC |
| Semgrep — OWASP Top 10 | latest | 0 findings (153 rules / 101 files) |
| Semgrep — Python | latest | 0 findings (151 rules / 101 files) |
| Semgrep — Secrets | latest | 0 findings (38 rules / 144 files) |
| Trivy fs | 0.69.3 | **2 HIGH + 1 MEDIUM** (uv.lock — 88 pkgs) |
| TruffleHog (verified) | 3.94.2 | 0 verified, 0 unverified (7,243 chunks) |
| OSV-Scanner | 2.3.5 | **2 HIGH + 1 MEDIUM** (uv.lock — 89 pkgs; matches Trivy) |

## Findings by severity

| Severity | Count |
|----------|------:|
| Very High | 0 |
| High | 2 (fixed) |
| Medium | 1 (fixed) |
| Low | 3 (fixed — `# nosec B110` with justification) |
| Info | 0 |

## High severity — fixed

### CVE-2026-44431 + CVE-2026-44432 — `urllib3` 2.6.3 → 2.7.0
- **Source:** Trivy + OSV-Scanner (GHSA-mf9v-mfxr-j63j CVSS 8.9; GHSA-qccp-gfcp-xxvc CVSS 8.2)
- **Titles:** Sensitive headers forwarded across origins in proxied low-level redirects; decompression-bomb safeguards bypassed in parts of the streaming API
- **Fix applied:** `uv lock --upgrade-package urllib3` → `urllib3 2.6.3 → 2.7.0`; `uv sync`
- **Re-scan:** OSV-Scanner clean

## Medium severity — fixed

### CVE-2026-44681 — `authlib` 1.6.11 → 1.7.2
- **Source:** Trivy + OSV-Scanner (GHSA-r95x-qfjj-fjj2, CVSS 6.1)
- **Title:** Authlib OIDC Implicit/Hybrid Authorization vulnerable to open redirect
- **Fix applied:** `uv lock --upgrade-package authlib` → `authlib 1.6.11 → 1.7.2` (added transitive `joserfc` 1.6.5); `uv sync`
- **Re-scan:** OSV-Scanner clean

## Low severity — fixed

3× Bandit B110 (`try/except/pass`) annotated with `# nosec B110` and a justification comment:
- `src/notebooklm_tools/cli/main.py:815` — best-effort update notification in a `finally` block; must never mask the real error
- `src/notebooklm_tools/utils/cdp.py:1066` — transient CDP error during page-load polling; retries until timeout
- `src/notebooklm_tools/utils/cdp.py:1284` — transient CDP error while polling for login; retries until timeout

Re-scan: Bandit 0 issues at all severities.

## Outcome

- **Risk posture before fix:** 2 HIGH + 1 MEDIUM (transitive dep CVEs) + 3 Low
- **Risk posture after fix:** Clean
- **Files changed by Phase 3:** `uv.lock` (urllib3 2.6.3 → 2.7.0, authlib 1.6.11 → 1.7.2, +joserfc 1.6.5; project version 0.6.6 → 0.6.9 by lock refresh), `src/notebooklm_tools/cli/main.py`, `src/notebooklm_tools/utils/cdp.py`
