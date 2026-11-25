# govcode-index

Dataset for the SHARE IT Federal Source Code Inventory

## About the Project

The gov-code dataset catalogs metadata about federal agency software projects.
It combines agency-published inventories and metadata collected from public
GitHub repositories. Coverage depends on configured sources, availability, and
metadata quality; it is not a complete census of every federal software project.

- [gov-code.json](gov-code.json): normalized project records grouped by agency.
- [gov-code.csv](gov-code.csv): one row per project, with 63 columns.
- [Data dictionary](docs/DATA_DICTIONARY.md): field definitions and transformations.

The dataset generation pipeline has six steps:

1. **Collect source metadata.** Download agency inventories configured in
   [agency-index-sources.json](sources/agency-index-sources.json), and collect
   repository `code.json` files from organizations configured in
   [public-sources.json](sources/public-sources.json) using
   `codejson-index-generator`. Save agency snapshots and assembled public indexes.
2. **Create or update project records.** Assign `govcode_id` when a project is
   first created. Match incoming records to existing projects and apply newer
   metadata while preserving their IDs and filenames.
3. **Normalize records.** Standardize structure, types, and values using the
   [normalization rules](docs/NORMALIZATION_RULES.md), including supplied CMS
   extension fields.
4. **Validate records.** Apply the [validation rules](docs/VALIDATION_RULES.md),
   log metadata issues, and fill required fields where supported. Identity and
   registry failures block consolidation; other checks are non-blocking.
5. **Consolidate JSON.** Combine processed projects into `gov-code.json`, an
   array of agency objects, each containing a `releases` array.
6. **Export CSV.** Flatten those releases into `gov-code.csv` for analysis.

GitHub Actions generates and commits both datasets. The pipeline performs local
validation and supplied-field diagnostics, not full remote project-schema
certification. Review collection warnings for skipped records and coverage gaps.

## Table of Contents

- [How It Works](#how-it-works)
- [Repository Structure](#repository-structure)
- [Agency Sources](#agency-sources)
- [Local Development](#local-development)
- [Output Formats](#output-formats)
- [Automation](#automation)
- [Known Limitations](#known-limitations)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Community](#community)
- [Policies](#policies)
- [Public domain](#public-domain)

## How It Works

```text
sources/agency-index-sources.json       sources/public-sources.json
                |                                   |
     pull_index_assets.py                 pull_public_assets.py
                +-----------------+-----------------+
                                  |
                    pull_all_assets.py runs both
                                  |
                 agency-indexes/{AGENCY}/*.json
                 agency-indexes/.govcode/*.json
                                  |
                  consolidate_to_gov_code.py
                                  |
                            gov-code.json
                                  |
                       gov_code_to_csv.py
                                  |
                            gov-code.csv
```

### 1. Collect inventories and public project metadata

[`pull_all_assets.py`](scripts/pull_all_assets.py) runs the agency-index
collector followed by the public-repository collector:

- [`pull_index_assets.py`](scripts/pull_index_assets.py) downloads configured
  agency indexes with a 30-second timeout. It rejects invalid JSON, preserves
  full source snapshots, and logs Windows-1252-to-UTF-8 conversion when needed.
- [`pull_public_assets.py`](scripts/pull_public_assets.py) uses
  `codejson-index-generator` to inspect public repositories in configured GitHub
  organizations. It reads root `code.json` files from default branches, skips
  missing files and agency-inventory wrappers, and saves an assembled public
  index for each agency. API failures are reported rather than treated as absent
  metadata.

The combined runner attempts both collectors even if the first fails. Without
`GITHUB_TOKEN`, it runs agency collection, skips public collection, and returns
nonzero to signal an incomplete refresh.

### 2. Match records and preserve local IDs

Both collectors share [matching logic](scripts/project_assets.py) and a
[persistent writer](scripts/govcode_ids.py). Within an agency, records match by
trimmed project name and normalized repository URL. A unique-name fallback is
allowed when a usable URL is unavailable and supplied URL evidence does not
conflict. Partial or ambiguous existing-record matches require review.

New projects receive an immutable ID such as `2026-DOE-000123`: first-assignment
UTC year, uppercase agency acronym, and an agency sequence number padded to at
least six digits. Numbers never reset or get reused. The committed
`agency-indexes/.govcode/` registry records allocation history and supports
recovery after interrupted writes. Its local `.lock` file is ignored by Git
and created automatically at runtime.

Matched updates retain their `govcode_id` and filename. They replace agency
content only when the latest recognized `lastModified` or
`metadataLastUpdated` timestamp (at top level or under `date`) is strictly newer.
Undated incoming updates retain the existing record with a warning.

Repeated incoming identities are handled before matching:

- Identical records collapse to one record.
- Different versions select the uniquely newest record only when every distinct
  version has a recognized timestamp.
- Unresolved duplicate groups are skipped with warnings. Existing records and
  IDs remain intact; new conflicted projects receive no ID. These skips alone
  do not fail the collector, so successful runs can still have coverage gaps.

New filenames come from project names: unsafe characters and whitespace become
underscores, stems are limited to 180 UTF-8 bytes, and case-insensitive
collisions receive `-2`, `-3`, and later suffixes. Changes to filenames are logged;
original names inside records are preserved. Missing or blank project names
fail identity resolution rather than creating anonymous project entries.

See [project identity rules](docs/PROJECT_IDENTITY.md) for URL normalization,
explicit rename mappings, recovery, and conflict handling.

### 3. Normalize, validate, and consolidate

[`consolidate_to_gov_code.py`](scripts/consolidate_to_gov_code.py) reads project
files, checks registry recovery state and IDs, and groups output by agency.
It fetches agency-schema configuration for valid agency acronyms, then:

1. Normalizes structures and values: legacy keys, types, URLs, dates, licenses,
   enums, and metadata fields.
2. Applies supplied-field diagnostics to HHS records using CMS metadata, based
   on the bundled [CMS 2.2.0 schema](scripts/schemas/cms-2.2.0.json). This does not
   establish CMS ownership or certify full CMS schema compliance.
3. Logs non-blocking record validation problems and fills required fields where
   supported by the available data.
4. Checks the local agency/release output contract before writing `gov-code.json`.

Agency-reported `identifier` remains separate from `govcode_id`. Legacy `id`
maps to `identifier`, numeric values become strings, and missing or blank
values become `null`. No identifier is invented from a repository URL or name.
Unknown enum values are not guessed; a repository URL alone does not establish
public visibility.

Missing, malformed, or duplicate `govcode_id` values, invalid registries, and
pending write journals block consolidation. Other record validation warnings
remain non-blocking. The fetched agency schema supplies configuration; the
pipeline does **not** enforce the full remote project schema.

### 4. Export CSV

[`gov_code_to_csv.py`](scripts/gov_code_to_csv.py) flattens `gov-code.json` into
`gov-code.csv`. It places `govcode_id` first, adds the parent agency, flattens
nested fields, and joins arrays with `|`. The export includes CMS extension
columns and preserves numeric zeros. It is a fixed-column analytical export,
not a lossless replacement for the JSON. See the [CSV guide](docs/CSV_DATASET.md).

## Repository Structure

```text
agency-indexes/
  {AGENCY}-index.json          Downloaded agency inventory
  {AGENCY}-public-index.json   Assembled public-repository inventory
  {AGENCY}/*.json              Project records with permanent local IDs
  .govcode/*.json              Committed ID registries and optional match mappings
sources/
  agency-index-sources.json    Agency acronym -> inventory URL
  public-sources.json          Agency acronym -> GitHub organizations
scripts/
  pull_all_assets.py           Combined collection entry point
  pull_index_assets.py         Agency-index collector
  pull_public_assets.py        Public-repository collector
  project_assets.py            Identity, duplicates, recency, and filenames
  govcode_ids.py               ID allocation and recoverable writes
  consolidate_to_gov_code.py   JSON dataset generation
  gov_code_to_csv.py           CSV export
  requirements.txt            Python dependencies
  utils/                      Normalization, validation, and schema helpers
  schemas/cms-2.2.0.json       Bundled CMS metadata schema
.github/workflows/            Collection, publication, tests, and maintenance
tests/                      Offline tests using temporary fixtures
docs/                       Data and processing documentation
gov-code.json               Committed JSON dataset
gov-code.csv                Committed CSV dataset
```

## Agency Sources

[`agency-index-sources.json`](sources/agency-index-sources.json) currently
configures DHS, DOD, DOE, EPA, FEC, GSA, HHS, NSF, SSA, USDA, and VA. This file is
the source of truth for inventory URLs.

[`public-sources.json`](sources/public-sources.json) additionally configures:

| Agency | GitHub organizations |
| :-- | :-- |
| GSA | `GSA-TTS`, `GSA-SHARE-IT`, `18F`, `presidential-innovation-fellows` |
| HHS | `HHS`, `CMSgov`, `CMS-Enterprise`, `DSACMS` |

To add a source, edit the appropriate configuration file. Use a consistent
uppercase agency key across both sources. Consolidation skips directories whose
agency acronym is absent from the fetched schema's agency enum. Creating an
agency directory alone does not enable collection.

## Local Development

Use Python 3.13 to match the GitHub Actions workflows. Collectors use POSIX file
locking and run on Linux/macOS. Install dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/requirements.txt
```

Dependencies include `jsonschema` and `codejson-index-generator`. Run these
commands from the repository root; default data paths are resolved relative
to the repository:

| Task | Command | Network |
| :-- | :-- | :-- |
| Offline tests | `python -m unittest discover -s tests -v` | No |
| Both collectors | `python scripts/pull_all_assets.py` | Yes; public collection needs `GITHUB_TOKEN` |
| Agency indexes only | `python scripts/pull_index_assets.py` | Yes |
| Public repositories only | `python scripts/pull_public_assets.py` | Yes; configure `GITHUB_TOKEN` |
| Consolidate JSON | `python scripts/consolidate_to_gov_code.py` | Yes, for agency-schema configuration |
| Export CSV | `python scripts/gov_code_to_csv.py` | No |

Set `GITHUB_TOKEN` in your shell environment for public collection; do not commit
it. In Actions, the refresh workflow supplies it from the `PUBLIC_ASSETS_TOKEN`
repository secret.

Collection updates project files, snapshots, and registries. Consolidation and
export overwrite their respective dataset files. For code-only changes, use the
offline tests, which mock network calls and write temporary fixtures. Run live
collection only when intentionally refreshing data. Do not delete an established
ID registry to retry a refresh or reset existing IDs.

## Output Formats

| Output | Contents |
| :-- | :-- |
| `agency-indexes/{AGENCY}-index.json` | Full downloaded agency inventory; legacy encoding may be converted to UTF-8. |
| `agency-indexes/{AGENCY}-public-index.json` | Inventory assembled by the public collector from repository metadata. |
| `agency-indexes/{AGENCY}/{project-name}.json` | Selected agency-provided project data plus local `govcode_id`, written as UTF-8 JSON. |
| `agency-indexes/.govcode/{AGENCY}.json` | Sequence counter, project identity associations, and pending-write recovery journal. |
| `gov-code.json` | JSON array of agency objects containing normalized `releases`. |
| `gov-code.csv` | UTF-8 CSV with one row per project and 63 fixed columns, starting with `govcode_id`. |

New and updated project JSON writes place `govcode_id` first. Consolidated
release objects also put it first, followed by required fields and other
metadata. Unchanged project files are not rewritten just to reorder keys.
Both final datasets are tracked in Git; the registry must be committed with
project changes. Import identifier columns as text in spreadsheet applications
to preserve leading zeros.

## Automation

All three collection, dataset, and unit-test workflows use Python 3.13.

| Workflow | Trigger | Purpose |
| :-- | :-- | :-- |
| [pull-all-assets.yml](.github/workflows/pull-all-assets.yml) | Mondays 09:17 UTC; manual | Runs both collectors and commits snapshots, projects, and ID registries. |
| [update-dataset.yml](.github/workflows/update-dataset.yml) | Mondays 10:30 UTC; manual | Builds and commits `gov-code.json`, then builds and commits `gov-code.csv`; uploads dataset artifacts with 30-day retention. |
| [run-tests.yml](.github/workflows/run-tests.yml) | PRs changing `agency-indexes/`, `scripts/`, `tests/`, or this workflow | Installs dependencies and runs the offline unittest suite. |
| [gitleaks.yml](.github/workflows/gitleaks.yml) | Pushes and PRs | Runs secret scanning. |

Other repository-maintenance workflows live in [.github/workflows/](.github/workflows/).
The structure updater looks for a README marker that this document does not
contain; the structure above is maintained manually.

Refreshes are serialized per branch. Collection uses `continue-on-error` so
successful agency updates are committed even if another agency fails; a final
step reports the incomplete run as failed. Review both errors and warnings,
including skipped duplicate groups.

Dataset generation has a separate schedule and concurrency group. It is
scheduled after collection but is not triggered by, or conditional on, a
successful collection run. JSON and CSV are committed in separate steps; a
later failure can leave them from different runs. Artifacts are uploaded when
files exist, including on failure, so check run status before treating an
artifact as newly generated.

## Known Limitations

- Coverage depends on source availability and metadata quality. Skipped incoming
  conflicts can leave existing records unchanged or omit new projects.
- Renames, URL changes, and ambiguous matches can require explicit review.
  Obsolete files are not automatically deleted.
- The legacy collector saves the full index before validating project structure
  and matching. A valid JSON response with invalid releases can replace the
  snapshot while project processing fails.
- Existing unregistered project files are rejected. Recovery or migration must
  preserve ID history; routine refresh is not a full reset operation.
- Validation is intentionally flexible. A successful build is not a guarantee
  of full remote-schema compliance or complete agency coverage.
- The agency `version` currently becomes `"string"`: the configuration helper
  reads the schema property's type rather than a version value. This is a known
  output limitation, not the project version.
- Default logging does not display consolidation's `INFO` messages. Warnings and
  errors remain visible.

## Documentation

| Document | Purpose |
| :-- | :-- |
| [PROJECT_IDENTITY.md](docs/PROJECT_IDENTITY.md) | Matching, IDs, duplicate decisions, mappings, and recovery |
| [NORMALIZATION_RULES.md](docs/NORMALIZATION_RULES.md) | Structural and value cleanup, including supplied CMS fields |
| [VALIDATION_RULES.md](docs/VALIDATION_RULES.md) | Validation, required-field filling, and local schema exceptions |
| [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Field definitions and JSON/CSV mappings |
| [CSV_DATASET.md](docs/CSV_DATASET.md) | CSV usage, flattening, and export limitations |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development and contribution workflow |
| [AGENTS.md](AGENTS.md) | Repository guidance for coding agents |

## Contributing

Thank you for considering contributing to an Open Source project of the US
Government! For setup, testing, and pull request guidelines, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Community

The govcode-index team is taking a community-first and open source approach to
this project. We believe government software should be made in the open and be
built and licensed such that anyone can download the code, run it themselves
without paying money to third parties or using proprietary software, and use it
as they will.

### Community Guidelines

Principles and guidelines for participating in our open source community can be
found in [COMMUNITY.md](COMMUNITY.md). All community members and participants
are expected to adhere to the community guidelines and
[code of conduct](CODE_OF_CONDUCT.md) when participating in community spaces,
including code repositories, communication channels and venues, and events.

### Governance

Information about how the govcode-index community is governed may be found in
[GOVERNANCE.md](GOVERNANCE.md).

## Feedback

To report a problem with the data or the scripts, or to suggest an agency to
add, please [file an issue](https://github.com/GSA-SHARE-IT/govcode-index/issues).
Problems in an agency's source inventory should also be raised with that agency.

## Policies

### Open Source Policy

We adhere to the [CMS Open Source
Policy](https://github.com/CMSGov/cms-open-source-policy). If you have any
questions, just [shoot us an email](mailto:opensource@cms.hhs.gov).

### Security and Responsible Disclosure Policy

_Submit a vulnerability:_ Vulnerability reports can be submitted through
[Bugcrowd](https://bugcrowd.com/cms-vdp). Reports may be submitted anonymously.
If you share contact information, we will acknowledge receipt of your report
within 3 business days.

For more information about our Security, Vulnerability, and Responsible
Disclosure Policies, see [SECURITY.md](SECURITY.md).

### Software Bill of Materials (SBOM)

A Software Bill of Materials (SBOM) is a formal record containing the details
and supply chain relationships of various components used in building software.

In the spirit of [Executive Order 14028 - Improving the Nation’s Cyber
Security](https://www.gsa.gov/technology/it-contract-vehicles-and-purchasing-programs/information-technology-category/it-security/executive-order-14028),
a SBOM for this repository is provided here:
https://github.com/GSA-SHARE-IT/govcode-index/network/dependencies.

For more information and resources about SBOMs, visit: https://www.cisa.gov/sbom.

## Public domain

This project is in the public domain within the United States, and copyright
and related rights in the work worldwide are waived through the [CC0 1.0
Universal public domain
dedication](https://creativecommons.org/publicdomain/zero/1.0/) as indicated in
[LICENSE](LICENSE).

All contributions to this project will be released under the CC0 dedication. By
submitting a pull request or issue, you are agreeing to comply with this waiver
of copyright interest.
