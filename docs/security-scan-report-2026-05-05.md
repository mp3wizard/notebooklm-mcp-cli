# Security Scan Report — 2026-05-05 (post-merge v0.6.4)

**Target:** `/Users/mp3wizard/Public/Notebook LM MCP with Claude/notebooklm-mcp-cli`
**Git HEAD:** `f6cc5bc` (merge of `origin/main` @ `bf75239`)
**Trigger:** Daily upstream sync — merged 5 commits from `origin/main` (v0.6.3 → v0.6.4)

## Upstream changes merged

| Commit | Type | Summary |
|--------|------|---------|
| `ffc0a58` | Fix | strip OSID cookies before cross-domain artifact downloads (PR #180, @laofun) |
| `bb3875c` | Merge | PR #180 |
| `afc6631` | Chore | align version strings to 0.6.4 |
| `6ee29ef` | Docs | update CHANGELOG for v0.6.3 and v0.6.4 |
| `bf75239` | Chore/CI | align manifest version + format `cdp.py` |

No security-classified upstream changes; the download fix is a functional auth-cookie scoping fix (cookies were being over-shared cross-domain → ServiceLogin redirect, not a privilege/secret leak).

## Tools run

| Tool | Version | Result |
|------|---------|--------|
| Gitleaks | 8.30.1 | 0 leaks (512 commits, 9.16 MB) |
| Bandit | 1.9.4 | 0 issues (22,414 LOC; 55 `# nosec` skipped) |
| Semgrep — OWASP Top 10 | latest | 0 findings (153 rules / 101 files) |
| Semgrep — Python | latest | 0 findings (151 rules / 101 files) |
| Semgrep — Secrets | latest | 0 findings (38 rules / 141 files) |
| Trivy fs | 0.69.3 | 0 vulnerabilities, 0 secrets (uv.lock — 88 pkgs) |
| TruffleHog (verified) | 3.94.2 | 0 verified, 0 unverified (7,063 chunks) |
| OSV-Scanner | 2.3.5 | 0 issues (uv.lock — 88 pkgs) |

## Findings by severity

| Severity | Count |
|----------|------:|
| Very High | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |
| Info | 0 |

## Fixes applied

None — clean across all tools.

## Notes

- Trivy 0.69.3 is the last version not affected by the GHSA-69fq-xp46-6x23 supply-chain advisory; v0.69.4–v0.69.6 are compromised. Trivy notice mentions 0.70.0 is available — upgrade in a later cycle when convenient.
- semgrep launched from `$HOME/.local/bin/semgrep` (pipx, linker-signed) per project policy.
- No `.env` or credential files present in the working directory.

## Conclusion

**Risk posture: Clean.** No remediation required. Documentation updated in `README.md` (v0.6.4 sync section + scan summary).
