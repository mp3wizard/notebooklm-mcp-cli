# v0.9.15 Maintenance Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver and verify v0.9.15 fixes for generic Studio file exports and Chromium-family authentication, enable private vulnerability reporting, and leave PR #309 ready for a separately verified v0.10.0 cycle.

**Architecture:** Keep raw NotebookLM payload interpretation in `core/`, service routing and validation in `services/`, and CLI/MCP wrappers thin. Type-10 artifacts are classified by MIME; a dedicated generic-file downloader resolves either a direct URL or the observed Drive viewer JSON envelope. Browser discovery gains one verified Comet candidate and one validated executable-path override.

**Tech Stack:** Python 3.11+, httpx, Pydantic, Typer, pytest, uv, Ruff, GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-08-26-maintenance-v0.9.15-design.md`

## Global Constraints

- Preserve existing `data_table_xlsx` behavior for the XLSX MIME exactly.
- Never download an envelope target unless it uses HTTPS and a trusted Google/Googleusercontent host.
- Every production behavior change starts with a focused test observed failing for the intended reason.
- `cli/` and `mcp/` remain thin wrappers and must not import `core/` directly.
- Do not change the three dirty files in Jacob's main checkout.
- Do not publish a GitHub release or PyPI package in this plan.

---

### Task 1: Classify type-10 exports by MIME

**Files:**
- Modify: `src/notebooklm_tools/core/studio.py`
- Modify: `src/notebooklm_tools/services/studio.py`
- Test: `tests/core/test_studio.py`
- Test: `tests/services/test_studio.py`

**Interfaces:**
- Consumes: raw `artifact[24]` file metadata.
- Produces: status artifacts with `type`, `download_filename`, and `mime_type`.

- [ ] **Step 1: Write the failing core tests**

Add one literal type-10 Markdown fixture whose metadata is `['analysis.md', 'text/markdown', 'https://drive.google.com/viewer/upload?ds=token']`. Assert `type == 'file'`, `download_filename == 'analysis.md'`, and `mime_type == 'text/markdown'`. Extend the existing XLSX test to assert its spreadsheet MIME and retain `type == 'data_table_xlsx'`.

- [ ] **Step 2: Verify the Markdown classification test fails**

Run: `uv run pytest tests/core/test_studio.py -k 'type_10 or xlsx_data_table' -v`

Expected: the Markdown artifact is incorrectly classified as `data_table_xlsx` and has no `mime_type`.

- [ ] **Step 3: Implement minimal MIME-driven classification**

Read filename and MIME from a valid `artifact[24]`. Map only `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` to `data_table_xlsx`; map other type-10 metadata to `file`. Add `mime_type` to the core result and service `ArtifactInfo` without exposing signed URLs.

- [ ] **Step 4: Add and run the service contract test**

Assert `get_studio_status()` preserves `mime_type` and `download_filename` for `file`, then run:

`uv run pytest tests/core/test_studio.py tests/services/test_studio.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -f docs/superpowers/specs/2026-08-26-maintenance-v0.9.15-design.md docs/superpowers/plans/2026-08-26-maintenance-v0.9.15.md
git add src/notebooklm_tools/core/studio.py src/notebooklm_tools/services/studio.py tests/core/test_studio.py tests/services/test_studio.py
git commit -m "fix: classify generic studio file exports"
```

### Task 2: Make generic file exports downloadable

**Files:**
- Modify: `src/notebooklm_tools/core/download.py`
- Modify: `src/notebooklm_tools/services/downloads.py`
- Modify: `src/notebooklm_tools/cli/commands/download.py`
- Modify: `src/notebooklm_tools/mcp/tools/downloads.py`
- Test: `tests/core/test_download.py`
- Test: `tests/services/test_downloads.py`
- Test: `tests/cli/test_downloads.py` or the existing download CLI test module selected by collection
- Test: `tests/test_mcp_downloads.py`

**Interfaces:**
- Consumes: type-10 metadata with either three or four fields.
- Produces: `NotebookLMClient.download_file(notebook_id: str, output_path: str, artifact_id: str | None = None) -> str`; service artifact type `file`; CLI command `nlm download file`.

- [ ] **Step 1: Write failing direct-download and viewer-envelope tests**

Use complete literal raw artifact fixtures. For the four-field fixture, assert the direct URL is streamed. For the three-field fixture, fake a viewer response of `{'pdf': 'https://doc-1-apps-viewer.googleusercontent.com/file.pdf'}` and assert the trusted target is streamed. Assert a non-Google target such as `https://evil.example/file.pdf` raises `ArtifactParseError` before any file is written.

- [ ] **Step 2: Verify failures are behavioral**

Run: `uv run pytest tests/core/test_download.py -k 'generic_file or viewer_envelope' -v`

Expected: FAIL because `download_file` does not exist; the tests must exercise the real resolver while mocking only external HTTP.

- [ ] **Step 3: Implement the core resolver and downloader**

Add narrowly scoped helpers that validate metadata, fetch the viewer envelope with authenticated httpx settings, select a trusted HTTPS URL, and delegate binary streaming to `_download_url_sync`. Preserve temp-file cleanup and structured `ArtifactParseError`/`ArtifactDownloadError` behavior.

- [ ] **Step 4: Write failing service routing and filename tests**

Assert `file` is accepted, sync/async dispatch calls `client.download_file`, bulk download uses the artifact filename, and a resolved PDF path is reported exactly. Run:

`uv run pytest tests/services/test_downloads.py -k 'file' -v`

Expected: FAIL because `file` is not yet a valid service type.

- [ ] **Step 5: Implement service, CLI, and MCP routing**

Add `file` to validation/default extension handling, route sync and async calls through `download_file`, add the simple `nlm download file` command, and document `file` in the MCP tool docstring. Do not duplicate download logic in either wrapper.

- [ ] **Step 6: Verify all affected interfaces**

Run:

```bash
uv run pytest tests/core/test_download.py tests/services/test_downloads.py tests/test_mcp_downloads.py tests/cli -k 'download' -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/notebooklm_tools/core/download.py src/notebooklm_tools/services/downloads.py src/notebooklm_tools/cli/commands/download.py src/notebooklm_tools/mcp/tools/downloads.py tests/core/test_download.py tests/services/test_downloads.py tests/test_mcp_downloads.py tests/cli
git commit -m "fix: download generic studio file exports"
```

### Task 3: Support Comet and arbitrary Chromium executables

**Files:**
- Modify: `src/notebooklm_tools/utils/config.py`
- Modify: `src/notebooklm_tools/utils/cdp.py`
- Modify: `src/notebooklm_tools/utils/auth_browser.py`
- Modify: `src/notebooklm_tools/cli/ai_docs.py`
- Modify: `src/notebooklm_tools/data/SKILL.md`
- Modify: `src/notebooklm_tools/data/references/command_reference.md`
- Test: `tests/test_auth_browser.py`
- Test: `tests/test_auth_migration.py`
- Test: the existing config test module found with `rg 'NLM_BROWSER' tests`

**Interfaces:**
- Consumes: `auth.browser_path` or `NLM_BROWSER_PATH`; named browser `comet`.
- Produces: validated executable discovery used by all existing CDP launch paths.

- [ ] **Step 1: Write failing config and discovery tests**

Assert `NLM_BROWSER_PATH` overrides the TOML value, config serialization preserves `browser_path`, `_get_chromium_path('comet')` selects a literal existing Comet executable in a patched macOS candidate table, and an explicit executable path wins over a detected Chrome candidate. Assert a nonexistent/non-file/non-executable explicit path returns no browser and does not fall back.

- [ ] **Step 2: Verify focused tests fail**

Run: `uv run pytest tests/test_auth_browser.py tests/test_auth_migration.py -k 'comet or browser_path' -v`

Expected: FAIL because the config field, env override, and Comet key do not exist.

- [ ] **Step 3: Implement minimal discovery changes**

Add nullable/empty-default `browser_path`, read `NLM_BROWSER_PATH`, serialize the value only through the existing config model, validate executable files with `Path.is_file()` plus platform-appropriate executable checks, and add Comet to the macOS candidates/config map/auth key set. Keep all launch sites using `get_chrome_path()` so the override is centralized.

- [ ] **Step 4: Verify authentication behavior and real local detection**

Run the focused tests, then run a read-only Python smoke probe with `preferred='comet'` and assert it returns `/Applications/Comet.app/Contents/MacOS/Comet` on this host. Do not launch or close the user's normal Comet profile; only test path discovery.

- [ ] **Step 5: Update user documentation and commit**

Document `comet`, `auth.browser_path`, and `NLM_BROWSER_PATH`, then run Ruff on touched files and commit:

```bash
git add src/notebooklm_tools/utils/config.py src/notebooklm_tools/utils/cdp.py src/notebooklm_tools/utils/auth_browser.py src/notebooklm_tools/cli/ai_docs.py src/notebooklm_tools/data/SKILL.md src/notebooklm_tools/data/references/command_reference.md tests
git commit -m "feat: support custom Chromium auth browsers"
```

### Task 4: Enable private vulnerability reporting

**Files:** None.

**Interfaces:**
- Produces: repository setting `private_vulnerability_reporting.enabled == true`.

- [ ] **Step 1: Read the current setting**

Run: `gh api repos/jacob-bd/gemini-notebook-mcp-cli/private-vulnerability-reporting`

Expected before change: `{"enabled":false}`.

- [ ] **Step 2: Enable and verify**

Run:

```bash
gh api --method PUT repos/jacob-bd/gemini-notebook-mcp-cli/private-vulnerability-reporting
gh api repos/jacob-bd/gemini-notebook-mcp-cli/private-vulnerability-reporting
```

Expected after change: `{"enabled":true}`.

- [ ] **Step 3: Notify and close #308**

Comment that the private reporting form is enabled and invite the prepared report, then close the issue. Re-read the issue state to verify closure.

### Task 5: Prepare v0.9.15 and verify locally

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `src/notebooklm_tools/__init__.py`
- Modify: `src/notebooklm_tools/data/SKILL.md`
- Modify: `src/notebooklm_tools/data/AGENTS_SECTION.md`
- Modify: `desktop-extension/manifest.json`

**Interfaces:**
- Produces: five aligned `0.9.15` declarations and release notes for #315/#302/#308.

- [ ] **Step 1: Add the changelog entry and align versions**

Create `0.9.15 - 2026-08-26` sections for Added, Fixed, Security, and Verification. Set all five version files to `0.9.15`.

- [ ] **Step 2: Run targeted regression tests**

```bash
uv run pytest tests/core/test_studio.py tests/core/test_download.py tests/services/test_studio.py tests/services/test_downloads.py tests/test_auth_browser.py tests/test_auth_migration.py tests/test_mcp_downloads.py -v
```

- [ ] **Step 3: Run complete local release gates**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not e2e" -q
uv build
```

Also execute the same five-file version comparison used by `.github/workflows/version-check.yml`. Expected: all commands exit 0.

- [ ] **Step 4: Reinstall and smoke-test the built CLI**

Per repository policy:

```bash
uv cache clean && uv tool install --force .
nlm --version
nlm download --help
```

Expected: version `0.9.15` and the new `file` download command. Use authenticated, read-only Studio status and one known type-10 artifact download if a valid local profile/notebook fixture is available; otherwise record that live provider coverage was unavailable and rely on the HTTP contract tests.

- [ ] **Step 5: Commit release preparation**

```bash
git add CHANGELOG.md pyproject.toml src/notebooklm_tools/__init__.py src/notebooklm_tools/data/SKILL.md src/notebooklm_tools/data/AGENTS_SECTION.md desktop-extension/manifest.json uv.lock
git commit -m "chore: prepare v0.9.15"
```

### Task 6: Integrate, prove remote CI, and close resolved issues

**Files:** None unless a genuine CI defect is found.

**Interfaces:**
- Consumes: verified maintenance branch commits.
- Produces: current main containing v0.9.15 preparation and a green GitHub Actions run.

- [ ] **Step 1: Review the complete branch diff**

Run `git diff --check origin/main...HEAD`, inspect `git diff --stat` and the full diff, and verify no unrelated files entered the branch.

- [ ] **Step 2: Integrate without overwriting Jacob's dirty checkout**

Push the maintenance branch and integrate through a fast-forward/merge operation that does not alter the dirty files. Do not publish a GitHub release.

- [ ] **Step 3: Restore the remote CI signal**

Cancel superseded permanently queued runs if necessary, dispatch or trigger a fresh run on the integrated SHA, and wait for both lint and tests to finish. If GitHub never assigns runners, report infrastructure blockage explicitly and do not call the release ready.

- [ ] **Step 4: Close only verified issues**

Comment on #315 with the new `file` status/download behavior and verification evidence; comment on #302 with Dia, Comet, and custom-path instructions. Close each only after the integrated SHA and CI evidence exist. Re-read issue states.

### Task 7: Harden PR #309 for v0.10.0

**Files:**
- Modify only the PR's existing seven files and focused Enterprise tests unless review proves another file is necessary.
- Add redacted request/response fixtures under `tests/fixtures/enterprise/` only when sourced from a real capture.

**Interfaces:**
- Consumes: integrated v0.9.15 main and PR head `a016eac45312b8787fab58003d383f828c03599d`.
- Produces: an updated contributor PR or clearly attributed owner replacement branch, with personal and Enterprise routing contracts tested.

- [ ] **Step 1: Update the actual PR branch**

Fetch the contributor head, rebase it on the new main, and push back to the PR branch if maintainer permissions permit. If the fork rejects pushes, create an owner branch preserving the contributor commit and open a replacement PR that links #309.

- [ ] **Step 2: Write failing compatibility tests before changing PR code**

Test personal host routing, Enterprise list routing, location handling, auth refresh, and streamed query URLs. The first Enterprise query test must pass `new_conversation=True` so no persistent-conversation network path runs before the behavior under test.

- [ ] **Step 3: Obtain evidence before enforcing project-ID rules**

Use a redacted live capture supplied by the contributor or a real Enterprise profile. Do not make project ID mandatory from conjecture. If no fixture is available, request it in the PR and mark live E2E confirmation pending.

- [ ] **Step 4: Run full review and verification**

Run focused tests, full non-E2E tests, Ruff, format, package build, and an adversarial code review. Leave PR #309 unmerged until the v0.10.0 release scope and live Enterprise evidence are approved.

