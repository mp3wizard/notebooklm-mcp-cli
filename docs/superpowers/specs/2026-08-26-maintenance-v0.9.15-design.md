# v0.9.15 Maintenance Release Design

## Goal

Ship a narrowly scoped maintenance release that prevents type-10 Studio exports from becoming unreachable, supports current and future Chromium-family browsers without requiring a new release for every fork, enables GitHub private vulnerability reporting, and restores trustworthy release gates. Enterprise support in PR #309 remains a separate v0.10.0 workstream.

## Scope

### Issue #315: generic Studio file exports

NotebookLM type code `10` is a generic file-export container. Its actual format is described by `artifact[24]`:

```text
[filename, mime_type, viewer_url, optional_direct_download_url]
```

The client must classify an XLSX MIME as `data_table_xlsx` for backward compatibility and classify every other valid type-10 export as `file`. Studio status must expose `download_filename` and `mime_type` so callers can make an informed choice.

`download_file(notebook_id, output_path, artifact_id=None)` must support both observed metadata shapes:

- Four fields: download the direct URL at index 3.
- Three fields: fetch the viewer URL at index 2, parse its JSON envelope, validate an HTTPS Google/Googleusercontent target, then download the target.

If the envelope identifies the target as PDF, a default path derived from the misleading `.md` source filename must be changed to `.pdf`. An explicit user-supplied path remains explicit, while the returned result always names the path actually written. Malformed metadata, malformed JSON, absent target URLs, non-HTTPS URLs, and untrusted hosts must fail with a structured artifact error; they must never write partial files.

The shared service and user interfaces must accept the additive `file` artifact type. The CLI receives `nlm download file`; MCP `download_artifact(..., artifact_type="file")` and bulk downloads route through the same service method. Existing `report`, `data_table`, and `data_table_xlsx` behavior remains unchanged.

### Issue #302: Chromium-family authentication

Dia is already supported on current main. Add explicit Comet support using the verified macOS executable path `/Applications/Comet.app/Contents/MacOS/Comet`, and add an escape hatch for any Chromium-compatible executable:

- Config: `auth.browser_path`
- Environment override: `NLM_BROWSER_PATH`

An explicit path takes precedence over named-browser discovery. It must point to an existing executable file; invalid values must not silently fall back to another browser. Named `comet` selection may fall back according to the existing named-browser policy when Comet is absent. Authentication continues to launch the selected executable with the existing isolated profile and CDP flags.

### Issue #308: private vulnerability reporting

Enable GitHub private vulnerability reporting with the bodyless repository API operation:

```bash
gh api --method PUT repos/jacob-bd/gemini-notebook-mcp-cli/private-vulnerability-reporting
```

Verify the repository API returns `enabled: true`, notify the reporter that the private intake is available, and close #308. A `SECURITY.md` file is not a prerequisite and is outside this maintenance release.

### CI and release preparation

The current main workflow run is queued without logs. A v0.9.15 release is not ready until:

- local targeted tests pass;
- the full non-E2E test suite passes;
- Ruff lint and format checks pass;
- a clean package builds;
- all five version declarations equal `0.9.15`;
- a fresh GitHub Actions run on the integrated commit completes successfully.

Prepare, but do not publish, the GitHub release. Publishing a GitHub release triggers PyPI publication and needs a separate explicit instruction from Jacob.

## Non-goals

- Do not merge PR #309 into v0.9.15.
- Do not guess Enterprise request contracts or require a GCP project ID without a captured, redacted fixture.
- Do not refactor unrelated Studio, download, authentication, or release code.
- Do not alter Jacob's dirty files in the main checkout.

## PR #309 follow-up for v0.10.0

After v0.9.15 is integrated and remotely green, update PR #309 against current main. Preserve contributor attribution. Add contract tests from redacted live Enterprise list/query requests, ensure the first query test uses `new_conversation=True`, and verify personal-account routing remains unchanged. If a live Enterprise account is unavailable, request fixtures from the contributor and clearly distinguish contract-test confidence from live E2E confirmation.

