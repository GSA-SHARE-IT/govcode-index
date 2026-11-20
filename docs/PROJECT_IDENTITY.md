# Project identity and local IDs

Both collectors use the same matcher and persistent writer. Source snapshots
remain agency-provided data; extracted project files add `govcode_id`.

## ID format and storage

`2026-DOE-000123` means first assigned in UTC year 2026, by DOE, with agency
sequence number 123. Numbers have at least six digits and never reset at the
new year. IDs and existing filenames remain unchanged on matched updates.
Project JSON writes place `govcode_id` first, including consolidated release
objects. CSV export places it in the first column. Existing files are not
rewritten solely to reorder keys; new or updated project writes use this order.
Agency `identifier` is unrelated to matching and is never generated locally.

The committed `agency-indexes/.govcode/{AGENCY}.json` registry stores the next
number, filename/identity associations (including disappeared files), and a
pending-write journal. Keep this directory when refreshing or rebuilding after
initial assignment. A missing registry alongside existing project files is an
error, not permission to reassign IDs. Incoming source `govcode_id` is rejected
as a reserved-field conflict rather than overwriting local metadata.

The writer locks the registry on Linux/macOS, records allocations and planned
writes atomically, then replaces individual project files atomically. An
interrupted run may leave a pending journal; rerunning that agency replays it
before planning new changes. Consolidation refuses pending transactions.
This is recoverable multi-file writing, not an atomic directory-wide swap.
The workflow already serializes refreshes and commits the registry because it
stages all of `agency-indexes/`. The local `.lock` file is ignored.

## Matching rules

Matching is agency-scoped. Compare exact names after trimming surrounding
whitespace and normalized repository URLs (HTTP/HTTPS scheme ignored, host
lowercased, trailing slash removed; GitHub paths case-insensitive with `.git`
removed). Do not use filenames or agency identifiers as matching keys.

- One name-and-URL match: retain its ID and filename.
- If either record has no usable repository key, permit a unique-name match
  only when the name is unique in both incoming and existing sets and supplied
  URL evidence does not conflict. Non-key URLs, such as bare homepages, are
  retained as evidence so differing homepages do not match accidentally.
- Only name or only URL matches: require review.
- Multiple existing candidates or multiple incoming claims: require review.
- Repeated incoming name/URL identities: collapse identical JSON objects
  (ignoring object key order). For different versions, select the uniquely
  newest complete record only when every distinct version has a recognized
  timestamp. Conflicting newest ties or any undated/invalid-date version cause
  the entire incoming identity group to be skipped with a warning. Existing
  project files and IDs are retained; new conflicted projects are omitted
  without allocating IDs. Other projects continue. Skips alone do not cause a
  nonzero exit status: check warnings for incomplete project coverage and fix
  the conflicting upstream code.json records. Older tied versions may be discarded when a uniquely newer version exists.
  Log the identity, reason, and retained source release position. Do not merge
  fields or modify source snapshots. Each resolved group receives at most one ID.
- Missing/blank names: require review.
- No candidate: assign a new ID and use existing filename cleanup/collision rules.

A batch failure publishes no newly planned project writes or allocations for
that agency. Other agencies continue; the collector returns nonzero. Recovery
of an earlier pending journal can occur before a new batch is rejected.
The legacy collector still saves the full source snapshot before project
validation; a project-match failure does not roll back that snapshot.

Fresh batches can contain distinct names sharing a catalog URL, or distinct
URLs sharing a name. Their full pairs must be distinct. Later partial matches
require review; sharing a URL does not by itself establish project identity.

## Explicit review mappings

For a confirmed rename or URL migration, create
`agency-indexes/.govcode/matches.json`:

```json
{
  "DOE": [
    {
      "name": "New project name",
      "repositoryURL": "https://github.com/example/new-repo",
      "filename": "Original_project_name.json"
    }
  ]
}
```

`name` matches the trimmed incoming name; `repositoryURL` matches the exact
incoming value (use null when absent). The filename must already be registered
or present. Mappings preserve one-to-one matching and do not bypass recency.
This mechanism resolves existing-project matches, not skipped incoming duplicate
conflicts, new projects with partial conflicts, or cross-agency transfers. Fix
skipped duplicates upstream; partial conflicts and transfers require a separately
reviewed data/mapping decision before collection proceeds.

## Recency and consolidation

After matching, use the latest valid `lastModified` or `metadataLastUpdated`,
at top level or under `date`. A strictly newer timestamp replaces agency
content while carrying the local ID forward. An incoming timestamp can replace
an undated old record. Equal/older timestamps retain the old record; no usable
incoming timestamp retains it with a warning. A returning registered file that
is absent on disk is restored under its old filename and ID.

Consolidation preserves `govcode_id`, rejects malformed/missing/duplicate IDs,
and includes `identifier: null` when the agency did not provide it. Legacy `id`
mapping and string cleanup remain. The local validation contract permits null
identifiers; the remote agency schema currently supplies configuration only,
not full project-schema validation.

## Initial rollout

This implementation does not alter existing inventories or backfill IDs.
Existing files without registered IDs fail refresh and consolidation. Deploy
with the separately planned staged rebuild: collect into a fresh output tree,
resolve ambiguous source records, verify all expected agencies and ID checks,
and only then replace existing data and commit the registry with it. Do not
run the routine partial-success workflow as a delete-and-rebuild operation.
A staged rebuild workflow is a separate rollout task.
