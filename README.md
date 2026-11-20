# govcode-index

A collection of federal agency software inventories (`code.json` files),
refreshed weekly and split into one JSON file per project.

## About the Project

Federal agencies publish inventories of their custom-developed software as
`code.json` files at the root of their websites (for example,
`https://www.energy.gov/code.json`). Each inventory lists the agency's projects
in a `releases` array.

This repository:

1. **Collects** each agency's inventory from the URLs in
   [`sources/agency-index-sources.json`](sources/agency-index-sources.json) and
   preserves the complete index as published.
2. **Extracts** every project object from the `releases` array into its own
   file, so individual projects can be browsed, diffed, and tracked over time.
3. **Consolidates** the project files into a single `gov-code.json` dataset,
   normalized and validated against the
   [agency index schema](https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json).

Complete downloaded indexes preserve agency data. Extracted project files add
a permanent local `govcode_id`; other normalization happens only in the
consolidated `gov-code.json` output. See [project identity rules](docs/PROJECT_IDENTITY.md).

## Table of Contents

- [How It Works](#how-it-works)
- [Repository Structure](#repository-structure)
- [Agency Sources](#agency-sources)
- [Local Development](#local-development)
- [Output Formats](#output-formats)
- [Automation](#automation)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)
- [Community](#community)
- [Policies](#policies)
- [Public domain](#public-domain)

## How It Works

```plaintext
sources/agency-index-sources.json
        │
        ▼
scripts/pull_index_assets.py          (weekly, GitHub Actions)
        │  download → parse JSON → save full index → split releases
        ▼
agency-indexes/{AGENCY}-index.json    complete index, as published
agency-indexes/{AGENCY}/{project}.json one file per project, plus govcode_id
        │
        ▼
scripts/consolidate_to_gov_code.py    (run manually)
        │  normalize → validate → fill required fields → schema-check
        ▼
gov-code.json                         consolidated dataset (not committed)
```

### Step 1: Download and extract (`pull_index_assets.py`)

For each agency in the sources file, the downloader:

- Requests the inventory with a 30-second timeout.
- Parses the response as JSON **before** writing anything, so an HTML error page
  cannot replace a good index. Responses that are not valid UTF-8 are decoded as
  Windows-1252, converted to UTF-8, and logged.
- Writes the complete index to `agency-indexes/{AGENCY}-index.json`.
- Checks that the index has a `releases` array of objects, then writes each
  project to `agency-indexes/{AGENCY}/{project-name}.json` as UTF-8 with the
  complete agency project object (including unknown fields) preserved, plus a
  locally assigned `govcode_id`. Matched records update only when newer.
  Repeated incoming identities collapse when identical, or select a uniquely
  newest fully dated version with a warning. Unresolved duplicate groups are
  skipped with warnings while other projects continue; existing records/IDs
  remain intact and new conflicted projects are omitted until fixed upstream.
- Continues with the remaining agencies if one fails, reports the error, and
  exits with status `1` if any agency failed.

Filenames are built from the project's `name`:

| Situation | Behavior |
| :-- | :-- |
| Characters such as `/ \ ( ) < > : " \| ? *`, whitespace, or control characters | Replaced with `_`. Leading or trailing `.` and spaces are trimmed. |
| Name longer than 180 UTF-8 bytes | Truncated to 180 bytes without splitting a character. |
| Missing or empty name | Saved as `unnamed-project.json`. |
| Two projects map to the same filename (case-insensitive) | Later ones get `-2`, `-3`, … suffixes, in release order. |

Every case in the table prints a `WARNING` to stderr with the agency, the
original name, the final filename, and the reason. Only the filename changes.
The JSON content always keeps the original name.

### Step 2: Consolidate (`consolidate_to_gov_code.py`)

The consolidation script reads every project file under `agency-indexes/` and
builds a schema-compliant agency index for each agency:

1. **Schema configuration.** Fetches the agency index schema to get the list of
   valid agency acronyms. Agency directories that are not in the schema's enum
   (after upper-casing) are skipped.
2. **Normalize** ([`scripts/utils/normalize.py`](scripts/utils/normalize.py)).
   Fixes record structure (legacy key renames, type coercion, removal of
   unexpected nested keys) and values (URLs, dates, licenses, `usageType`,
   `status`, tags, emails). See
   [docs/NORMALIZATION_RULES.md](docs/NORMALIZATION_RULES.md).
3. **Validate** ([`scripts/utils/validate.py`](scripts/utils/validate.py)).
   Checks required fields, types, and enum values. Validation is non-blocking:
   problems are logged as warnings and the record is kept.
4. **Fill** (`fill_record`). Derives missing required fields where possible:
   `organization`, `repositoryVisibility`, `vcs`, and
   `feedbackMechanism`. Enum fields such as `status` and `maintenance` are never
   guessed. See [docs/VALIDATION_RULES.md](docs/VALIDATION_RULES.md).
5. **Schema-check** each agency index (`version`, `agency`, `releases`) with
   [`scripts/utils/schema.py`](scripts/utils/schema.py), then write all indexes
   to `gov-code.json` at the repository root.

## Repository Structure

```plaintext
.
├── .github/
│   ├── ISSUE_TEMPLATE/          # Issue templates for access and code.json requests
│   ├── codejson/                # Cookiecutter template for this repo's own code.json
│   └── workflows/               # GitHub Actions (data refresh, tests, repo hygiene)
├── agency-indexes/
│   ├── {AGENCY}-index.json      # Complete index as published by each agency
│   └── {AGENCY}/                # One JSON file per project in that agency's releases
├── docs/
│   ├── DATA_DICTIONARY.md       # Definitions of every field in the source data and gov-code.json
│   ├── NORMALIZATION_RULES.md   # Every normalization rule applied during consolidation
│   └── VALIDATION_RULES.md      # Validation checks and required-field filling rules
├── scripts/
│   ├── pull_index_assets.py     # Downloads indexes and extracts project files
│   ├── consolidate_to_gov_code.py  # Builds gov-code.json from project files
│   └── utils/
│       ├── normalize.py         # Structural and value normalization of project records
│       ├── validate.py          # Record validation and required-field filling
│       └── schema.py            # Schema fetching and agency index validation
├── sources/
│   └── agency-index-sources.json  # Agency acronym → code.json URL
├── tests/                       # Offline unittest suite (no network access)
└── requirements.txt             # Python dependencies (jsonschema)
```

### Top-level documents

| File | Description |
| :-- | :-- |
| [README.md](README.md) | Project overview, usage, and structure (this file) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to set up, test, and submit changes |
| [COMMUNITY.md](COMMUNITY.md) | Project members, roles, and community guidelines |
| [GOVERNANCE.md](GOVERNANCE.md) | How decisions are made |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Expected behavior in project spaces |
| [SECURITY.md](SECURITY.md) | How to report vulnerabilities |
| [AGENTS.md](AGENTS.md) | Guidance for AI coding agents working in this repository |
| [LICENSE](LICENSE) | CC0 1.0 Universal public domain dedication |

## Agency Sources

Agency URLs are kept in
[`sources/agency-index-sources.json`](sources/agency-index-sources.json), not in
code. The current sources are:

| Agency | Source |
| :-- | :-- |
| USDA | https://usda.gov/code.json |
| DoD | https://www.code.mil/code.json |
| DoE | https://www.energy.gov/code.json |
| HHS | https://www.hhs.gov/code.json |
| DHS | https://www.dhs.gov/code.json |
| VA | https://www.va.gov/code.json |
| EPA | https://www.epa.gov/code.json |
| NSF | https://www.nsf.gov/code.json |
| SSA | https://www.ssa.gov/code.json |
| FEC | https://www.fec.gov/code.json |

To add an agency, add an `"ACRONYM": "URL"` entry to the sources file. The key
becomes the output filename (`{ACRONYM}-index.json`) and directory name. For the
agency to appear in `gov-code.json`, the upper-cased key must also be a valid
agency in the agency index schema.

## Local Development

### Prerequisites

- Python 3.12 (the version the workflows use; newer versions also work)
- `pip install -r requirements.txt` (installs `jsonschema`, which the
  consolidation script and the test suite import)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the tests

The tests are offline. They mock network responses and use temporary
directories, so they never touch the real inventory files.

```bash
python3 -m unittest discover -s tests -v
```

### Refresh the agency indexes

This downloads every inventory and **overwrites** files under
`agency-indexes/`. Run it only when you intend to refresh the data.

```bash
python3 scripts/pull_index_assets.py
```

### Build the consolidated dataset

This needs network access to fetch the agency index schema. It writes
`gov-code.json` to the repository root.

```bash
python3 scripts/consolidate_to_gov_code.py
```

Records that fail validation are logged as warnings and still included. The
script exits with status `1` if the schema cannot be fetched or no agency
indexes are produced.

## Output Formats

For definitions of every field, allowed values, and how each field changes in
`gov-code.json`, see the [data dictionary](docs/DATA_DICTIONARY.md).

### `agency-indexes/{AGENCY}-index.json`

The agency's inventory exactly as downloaded (re-encoded as UTF-8 only if the
source was Windows-1252). Its structure follows whatever schema version the
agency publishes, typically:

```json
{
  "version": "2.0.0",
  "agency": "DOE",
  "measurementType": { "method": "projects" },
  "releases": [ { "name": "...", "repositoryURL": "...", "...": "..." } ]
}
```

### `agency-indexes/{AGENCY}/{project-name}.json`

One object from `releases`, saved with four-space indentation and non-ASCII
characters kept as-is. Agency fields are preserved and `govcode_id` is added.
The committed `agency-indexes/.govcode/` registry retains ID allocation history
and interrupted-write recovery state; never delete it after IDs are assigned.

### `gov-code.json`

A JSON array with one agency index object per agency:

```json
[
  {
    "version": "...",
    "agency": "DHS",
    "releases": [ { "name": "...", "identifier": "...", "...": "..." } ]
  }
]
```

Each release is normalized, then filled so that every required field is present.
`govcode_id` is required and globally unique; invalid or missing IDs stop the
build. Agency `identifier` values are no longer generated: missing values become
`null`. `govcode_id` comes first, followed by required fields in schema order. A required field is `null` when its
value could not be derived. `gov-code.json` is generated locally and is not
committed to the repository.

## Automation

| Workflow | Trigger | Purpose |
| :-- | :-- | :-- |
| [`pull-index-assets.yml`](.github/workflows/pull-index-assets.yml) | Mondays 09:17 UTC, manual | Runs the downloader and commits any changes under `agency-indexes/` as `chore: update agency indexes`. |
| [`run-tests.yml`](.github/workflows/run-tests.yml) | PRs touching `scripts/`, `tests/`, or the workflow | Installs `requirements.txt` and runs the unittest suite on Python 3.12. |
| [`gitleaks.yml`](.github/workflows/gitleaks.yml) | Every push and PR | Scans for committed secrets. |
| [`repoStructure.yml`](.github/workflows/repoStructure.yml) | Push to `main`, manual | Replaces a `
```plaintext
.
```
` marker in this README with `tree -d` output. The README does not use the marker, so the structure above is maintained by hand. |

The data refresh step uses `continue-on-error`, so successfully downloaded
agencies are still committed when another agency fails. Check the run log for
`Failed {AGENCY}` and `WARNING` lines.

## Known Limitations

- **Matching requires name and URL agreement.** Partial matches require review;
  a unique name fallback is available for missing/unusable URLs without conflict.
  Existing filenames are retained. See [identity rules](docs/PROJECT_IDENTITY.md).
- **Initial filename suffixes depend on release order.** Reordering later
  refreshes does not rename matched files. Obsolete files are not deleted.
- **Existing files without local IDs require the planned staged rebuild.**
  Collectors refuse to silently assign IDs to unregistered existing files.
- **`releases` is validated after the full index is saved.** Invalid JSON never
  overwrites an index, but a valid JSON response without a usable `releases`
  array does replace `{AGENCY}-index.json` before the agency is reported as
  failed.
- **Stable project IDs are not used for filenames yet.** Switching would require
  checking ID coverage and uniqueness per agency, a fallback for missing IDs,
  and a migration of existing files.
- **The consolidation script is not run in CI**, and its `INFO` progress messages
  are not shown because logging is not configured. Validation warnings and
  errors still print.
- **`gov-code.json` has a placeholder `version`.** The script reads the schema's
  `version` property type instead of a version number, so each agency index in
  the output currently has `"version": "string"`.

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
