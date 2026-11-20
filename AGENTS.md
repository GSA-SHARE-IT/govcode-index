# Repository guidance

## Purpose and layout

This repository collects federal agency software inventories, preserving each
agency's full JSON index and extracting individual project objects from its
`releases` array. A separate script normalizes, validates, and combines those
project files into a single `gov-code.json` dataset.

- `sources/agency-index-sources.json`: agency names and source URLs.
- `scripts/pull_index_assets.py`: downloads, validates, and saves inventories.
- `agency-indexes/{AGENCY}-index.json`: complete agency indexes.
- `agency-indexes/{AGENCY}/{project-name}.json`: individual project records.
- `scripts/consolidate_to_gov_code.py`: builds `gov-code.json` (generated
  locally, not committed) from the project files; fetches the agency index schema.
- `scripts/utils/`: `normalize.py`, `validate.py`, and `schema.py` used by the
  consolidation script. Their rules are documented in `docs/NORMALIZATION_RULES.md`
  and `docs/VALIDATION_RULES.md`.
- `tests/`: offline tests for the downloader, normalization, and validation.
- `.github/workflows/pull-index-assets.yml`: weekly and manually triggered
  refreshes. The download step uses `continue-on-error`, so changed outputs are
  committed even when some agencies fail.
- `.github/workflows/run-tests.yml`: PR tests for changes to `scripts/`,
  `tests/`, or the test workflow.

Consult `README.md` and `CONTRIBUTING.md` for additional repository context.

## Development conventions

- Follow the existing Python style and prefer the standard library where practical.
- Keep code compatible with Python 3.12, which the workflows use.
- Resolve data paths relative to the repository, not the caller's working directory.
- Keep agency URLs in the source JSON rather than duplicating them in code.
- Keep changes focused on the requested task and preserve unrelated local edits.

## Data handling

- Preserve complete project objects, including unknown fields and original names.
  Filename cleanup must not change values inside the JSON.
- Keep generated filenames within their agency directory and prevent silent
  overwrites from filename collisions, including case-insensitive collisions.
- Retain visible warnings for filename sanitization, truncation, duplicate
  suffixes, and missing names. Include the original name, final filename, and reason.
- Save generated project JSON as UTF-8. Preserve the logged Windows-1252 fallback
  for legacy responses unless intentionally changing encoding behavior.
- Continue processing other agencies after an agency failure, report the error,
  and return a nonzero exit status if any agency fails.
- Treat indexes and project files as generated outputs. For code-only changes,
  use temporary fixtures rather than refreshing or rewriting the real inventories.
  Run live downloads when the task calls for a data refresh.

## Current behavior and design decisions

- Filenames use project names. Stable IDs are a future option; assess ID coverage,
  uniqueness, missing-ID fallbacks, and migration effects before switching.
- Match agency-scoped trimmed name plus normalized repository URL. Unique-name
  fallback requires no conflicting URL. Ambiguities fail the agency before
  project writes; only newer matches replace content. Retain filenames and IDs.
- Collapse identical incoming name/URL records; select a uniquely newest
  version only if every distinct version has a valid timestamp. Log selections;
  skip conflicting newest ties or missing timestamps with warnings, retaining
  existing records/IDs and allocating nothing for skipped new projects. Other
  projects continue; duplicate skips alone do not fail the collector.
- `govcode_id` is local immutable metadata. Keep the committed
  `agency-indexes/.govcode/` registry with project outputs; never reset counters.
  Existing unregistered files require the staged rebuild. Do not refresh real
  data for code-only work. See `docs/PROJECT_IDENTITY.md`.
- Consolidation preserves agency `identifier` or fills null; never derive it.
  Missing/invalid/duplicate `govcode_id` values block consolidation.
- Obsolete files are not automatically deleted. Initial filename suffixes
  depend on release order; matched files retain their filenames.
- Invalid JSON is rejected before writing the full index. Validation of the
  `releases` structure currently happens after saving that index; do not assume
  all validation failures preserve the previous index.

These describe current behavior, not a prohibition on requested improvements.
Update the tests and relevant documentation when changing these behaviors.

## Commands and testing

Run offline tests from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Run a live refresh when needed:

```bash
python3 scripts/pull_index_assets.py
```

Build the consolidated dataset (needs network access for the schema):

```bash
python3 scripts/consolidate_to_gov_code.py
```

- Add or update relevant tests for behavior changes and run the suite before
  completing Python changes. Install `requirements.txt` first; the tests import
  `scripts.utils`, which requires `jsonschema`.
- Mock network responses and use temporary directories in tests. Tests must not
  depend on live agency availability or modify the real inventory files.
- Cover data preservation, encoding, filename collisions and warnings, and failure
  handling when changes affect those areas.
- For workflow changes, validate the YAML and check referenced commands and paths.

## Documentation and handoff

- Update documentation when commands, output layout, or processing behavior change.
  Normalization and validation rule changes also belong in the matching `docs/` file.
- Keep this file concise and focused on durable guidance. Use issues and PRs for
  future work and development history rather than copying session logs here.
- Report what changed, what validation ran, and any remaining limitations. Distinguish
  offline test results from live download or GitHub Actions results.
