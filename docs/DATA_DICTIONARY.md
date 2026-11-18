# Data Dictionary

This document defines every field found in the data, at two levels:

- **Source files** (`agency-indexes/`) are stored exactly as agencies publish
  them. Agencies publish the code.gov **code.json 2.0.0** metadata format, with
  some legacy and non-standard keys.
- **`gov-code.json`** targets the
  [**code.json 0.1.0** project schema](https://gsa-share-it.github.io/codejson-schemas/schemas/schema-0.1.0.json)
  inside the
  [agency index schema 1.0.0](https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json).
  It adds several required fields that 2.0.0 does not have.

**How to read the tables:**

- **Req.** ✔ means the field is required by the 0.1.0 schema. `fill_record`
  always includes required fields in `gov-code.json`, using `null`, `[]`, or `{}`
  when no value can be derived.
- **Source fill** is the share of the 8,045 project files under
  `agency-indexes/` where the field is present and not empty, as of the
  2026-11-18 refresh. It changes with each weekly refresh. "New" means the
  field is defined only in 0.1.0 and agencies do not currently publish it.

## Contents

- [Agency index object](#agency-index-object)
- [Project record](#project-record)
- [How `gov-code.json` changes each field](#how-gov-codejson-changes-each-field)
- [Legacy and non-standard keys in source data](#legacy-and-non-standard-keys-in-source-data)
- [Enumerations](#enumerations)

## Agency index object

The top-level object in `{AGENCY}-index.json` and in each element of the
`gov-code.json` array.

| Field | Type | Description | Source values | In `gov-code.json` |
| :-- | :-- | :-- | :-- | :-- |
| `version` | string | Version of the metadata schema the index uses. | `2.0.0` (HHS publishes `2.0`) | Currently the literal `"string"` (see [Known Limitations](../README.md#known-limitations)). |
| `agency` | string | Agency acronym. | Upper case, e.g. `DOE`, `DOD` | Upper-cased directory name. Must be one of the schema's [agency acronyms](#agency). |
| `measurementType` | object | How the agency counts its inventory. | `method` is `projects`, `modules`, or `other`. `ifOther` explains `other`. | Not included. |
| `releases` | array of objects | One [project record](#project-record) per entry. | 7 (FEC) to 5,879 (DoE) entries | Normalized and filled project records. |

## Project record

One element of `releases`. Each file in `agency-indexes/{AGENCY}/` holds one
project record.

### Identity and description

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `name` | string | ✔ | Name of the project or software. Also used to build the project's filename. | 100% |
| `identifier` | string | ✔ | Persistent unique ID that follows the project across renames and migrations. | New (1.8% have legacy `id`) |
| `version` | string | | Version of this release, for example `1.0.0`. | 15% |
| `description` | string | | One- or two-sentence description of the software. | 96% |
| `organization` | string | ✔ | Organization or component within the agency that owns the project, for example `18F`, `Navy`, or a national laboratory. | 98% |
| `tags` | array of strings | | Topics and keywords that help people find the project. | 99.7% |

### Status and maintenance

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `status` | string ([enum](#status)) | ✔ | Development status of the project. | 98% |
| `maintenance` | string ([enum](#maintenance)) | ✔ | Who keeps the software up to date, if anyone. | New |
| `vcs` | string ([enum](#vcs)) | | Version control system used. | 85% |

### Repository and links

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `repositoryURL` | URI, or `"private"` | ✔ | URL of the public repository. Closed-source projects may use `"private"`. Not required for government-wide reuse or exempt code. | 98% |
| `repositoryVisibility` | string ([enum](#repositoryvisibility)) | ✔ | Whether the repository is public or private. | New |
| `homepageURL` | URI | | URL of the project's public homepage. | 35% |
| `downloadURL` | URI | | URL where a distribution of the release can be downloaded. | 24% |
| `disclaimerURL` | URI | | URL of disclaimer language for the release. | 8.9% |
| `disclaimerText` | string | | Short paragraph of disclaimer language. | 1.8% |
| `feedbackMechanism` | URI | ✔ | How the project receives feedback, for example a GitHub issues page. | New |

### Permissions

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `permissions` | object | ✔ | Usage rights and restrictions for the release. | 99.9% |
| `permissions.licenses` | array of objects | | Licenses that apply to the release. Some source files have `null`. | 92% |
| `permissions.licenses[].name` | string ([enum](#license-names)) | | Short name of the license. | |
| `permissions.licenses[].URL` | URI | | URL of the license text. | |
| `permissions.usageType` | string in source; array of strings in `gov-code.json` ([enum](#usagetype)) | | Whether the code is open source, shared for government-wide reuse, or exempt, and under which exemption. | 99.9% |
| `permissions.exemptionText` | string or `null` | | One- or two-sentence justification when `usageType` is an exemption. | 4.9% |

### Dates

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `date` | object | | Dates describing the release. | 98% |
| `date.created` | date-time | | When the project was created. | 98% |
| `date.lastModified` | date-time | | When the project was last modified. | 25% |
| `date.metadataLastUpdated` | date-time | | When this metadata was last updated. | 91% |

Source dates are usually `YYYY-MM-DD`, and some use full ISO 8601 timestamps.
`gov-code.json` uses RFC 3339 throughout, for example `2024-04-02T00:00:00Z`.

### Contact

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `contact` | object | ✔ | Point of contact for the release. | 100% |
| `contact.email` | email | | Email address of the point of contact. | 92% |
| `contact.name` | string | | Name of the point of contact. | 19% |
| `contact.URL` | URI | | Contact web page (2.0.0 only). | 9.8% |
| `contact.phone` | string | | Contact phone number (2.0.0 only). | 2.2% |

### Effort and composition

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `laborHours` | number ≥ 0 | | Estimated labor hours invested, calculated with the COCOMO model in [scc](https://github.com/boyter/scc#cocomo). | 100% (49% are `0`) |
| `languages` | array of strings | | Programming languages in the codebase. | 35% |

### Related software

| Field | Type | Req. | Description | Source fill |
| :-- | :-- | :-: | :-- | --: |
| `relatedCode` | array of objects | | Affiliated government repositories that are part of the same project. Each item has `name`, `URL`, and `isGovernmentRepo` (boolean). | 0.1% |
| `reusedCode` | array of objects | | Government software, libraries, or platforms used in this release. Each item has `name` and `URL`. | <0.1% |
| `partners` | array of objects | | Partner agencies on the release. Each item has `name` (agency acronym) and `email` (contact at that agency). | 0% |

### Fields new in code.json 0.1.0

Agencies do not currently publish these fields.

| Field | Type | Req. | Description |
| :-- | :-- | :-: | :-- |
| `reuseFrequency` | object | ✔ | How often the code is reused: `forks`, `clones`, and `downloads`, each an integer ≥ 0. |
| `contractNumber` | array of strings | ✔ | Contract numbers under which the project was developed. |
| `SBOM` | string | | Link to the project's Software Bill of Materials, or `None` if it has none. |
| `AIUseCaseID` | string | | The software's ID in the AI Use Case Inventory, or `0` if it is not listed. |

The `identifier`, `repositoryVisibility`, `maintenance`, and
`feedbackMechanism` fields above are also new in 0.1.0.

## How `gov-code.json` changes each field

Source files are never modified. These changes apply only to the consolidated
output. The full rules are in
[NORMALIZATION_RULES.md](NORMALIZATION_RULES.md) and
[VALIDATION_RULES.md](VALIDATION_RULES.md).

| Field | Normalization and filling |
| :-- | :-- |
| All strings | Leading and trailing whitespace is trimmed. An empty optional string is removed. An empty required string becomes `null`. |
| `identifier` | Legacy `id` is renamed. Otherwise the value is derived from `repositoryURL` as lower-case `host/path` (for example `github.com/cisagov/acid`). Without a usable URL it becomes `{agency}:{name-slug}-{first 8 hex chars of SHA-1}`. |
| `organization` | Missing values are filled with the agency acronym. |
| `version` | Numbers are converted to strings. Empty or `null` values are removed. |
| `status` | Known spellings are mapped to the enum, for example `rc` → `Release Candidate` and `Alpha v0.11 (Prototype)` → `Alpha`. Unmappable values become `null`. Missing values are never guessed. |
| `maintenance` | Lower-cased if valid, otherwise `null`. Missing values are never guessed, so this is currently `null` for every record. |
| `vcs` | Lower-cased if valid. Invalid values (for example `zip`) are removed. Missing values become `git` when `repositoryURL` is a github.com repository. |
| `repositoryURL` | `http` is upgraded to `https`, the host is lower-cased, and a trailing `/` or `.git` is removed. A bare domain with no path is moved to `homepageURL`. Invalid URLs become `null`. A missing URL on closed code becomes `"private"`. |
| `repositoryVisibility` | Inferred: `private` when `repositoryURL` is `"private"`, `public` when it is a usable URL, otherwise `null`. |
| `homepageURL`, `downloadURL`, `disclaimerURL` | Legacy `homepage` is renamed to `homepageURL`. `http` is upgraded to `https`. Invalid URLs are removed. |
| `feedbackMechanism` | Missing values become `https://github.com/{owner}/{repo}/issues` for github.com repositories, otherwise `null`. |
| `permissions` | A missing object becomes `{"licenses": [], "usageType": []}`. Keys other than `licenses`, `usageType`, and `exemptionText` are removed. |
| `permissions.licenses` | `null` becomes `[]`, and a single object is wrapped in an array. Names are mapped to the [license enum](#license-names). Unrecognized names become `Other`, and `NOASSERTION` entries are dropped. Duplicates are removed. |
| `permissions.usageType` | A single string is wrapped in an array, and capitalization is corrected. Unrecognized values are dropped. Legacy `exemptByLaw`, `exemptByAgencySystem`, and `exemptByAgencyMission` are kept. Legacy `openSourceProject: 1` and `governmentWideReuseProject: 1` add `openSource` and `governmentWideReuse`. |
| `permissions.exemptionText` | A top-level `exemptionText` is moved here. An empty value becomes `null`. |
| `date.*` | Converted to RFC 3339. Date-only values get midnight UTC. `YYYY/MM/DD` and text dates such as `March 5, 2024` are parsed. Unparseable dates are removed. Legacy `updated` is moved to `date.lastModified`. |
| `contact` | A missing object becomes `{}`. Only `email` and `name` are kept, so `URL` and `phone` are removed. A malformed `email` becomes `null`. |
| `tags` | Lower-cased, whitespace collapsed, duplicates removed. A single string is wrapped in an array. |
| `languages` | Trimmed and de-duplicated. `"None"` and empty entries are removed, and an empty array is removed. |
| `laborHours` | Numeric strings are converted to numbers. Values of `0` or below are removed. |
| `relatedCode`, `reusedCode`, `partners` | Keys not listed in this dictionary are removed. Empty items are dropped, and an empty array is removed. |
| `reuseFrequency`, `contractNumber` | A missing `reuseFrequency` becomes `{}`, and a missing `contractNumber` becomes `[]`. |
| Field order | Required fields come first, in schema order, followed by all other fields in source order. |
| Unknown top-level keys | Kept as-is (for example `repoURL` and `exemption`). The empty-string key `""` is removed. |

## Legacy and non-standard keys in source data

A few source records use keys outside code.json 2.0.0. They are preserved in
`agency-indexes/` and handled as follows in `gov-code.json`. A renamed or moved
key is used only when the standard field is missing or empty. Otherwise the
legacy key is dropped.

| Source key | Records | Handling in `gov-code.json` |
| :-- | --: | :-- |
| `id` | 148 | Renamed to `identifier` |
| `repository` | 1 | Renamed to `repositoryURL` |
| `homepage` | 1 | Renamed to `homepageURL` |
| `updated` | 1 | Moved to `date.lastModified`. The current record's value is an object, not a date string, so it is then dropped. |
| `exemptionText` (top level) | 1 | Moved to `permissions.exemptionText` |
| `openSourceProject`, `governmentWideReuseProject` | 1 | Converted to `permissions.usageType` values, then removed |
| `contact.URL`, `contact.phone` | 785 / 180 | Removed |
| `repoURL`, `exemption` | 1 | Kept unchanged |
| `""` (empty key) | 1 | Removed |

## Enumerations

### `status`

| Value | Records in source |
| :-- | --: |
| `Ideation` | 2 |
| `Development` | 3,554 |
| `Alpha` | 0 (1 mapped from a variant) |
| `Beta` | 8 |
| `Release Candidate` | 1 |
| `Production` | 4,293 |
| `Archival` | 29 |

### `usageType`

| Value | Meaning | Records in source |
| :-- | :-- | --: |
| `openSource` | Released as open source. | 7,372 |
| `governmentWideReuse` | Available for reuse across the federal government. | 187 |
| `exemptByNationalSecurity` | Primarily for use in a national security system (40 U.S.C. § 11103). | 4 |
| `exemptByNationalIntelligence` | Developed by an element of the intelligence community. | 0 |
| `exemptByFOIA` | Exempt under the Freedom of Information Act. | 0 |
| `exemptByEAR` | Exempt under the Export Administration Regulations. | 0 |
| `exemptByITAR` | Exempt under the International Traffic in Arms Regulations. | 0 |
| `exemptByTSA` | Exempt under TSA rules protecting Sensitive Security Information. | 0 |
| `exemptByClassifiedInformation` | Exempt under laws governing classified information not covered above. | 0 |
| `exemptByPrivacyRisk` | Sharing would create an identifiable privacy risk to an individual. | 0 |
| `exemptByDisposableCode` | Written for one-time or short-term use and not meant to be reused. | 0 |
| `exemptByExperimentalCode` | Exploratory code not meant for production or reuse. | 0 |
| `exemptByCommercialSoftware` | Commercial or COTS software, or configuration scripts for it. | 0 |
| `exemptByLaw` | *Legacy (2.0.0).* Sharing is restricted by law or regulation, such as patent law, export rules, or classified-information rules. Kept in `gov-code.json`. | 374 |
| `exemptByAgencySystem` | *Legacy (2.0.0).* Sharing would put the stability, security, or integrity of the agency's systems or personnel at identifiable risk. Kept. | 54 |
| `exemptByAgencyMission` | *Legacy (2.0.0).* Sharing would put the agency's mission, programs, or operations at identifiable risk. Kept. | 46 |

### License names

Allowed values in `gov-code.json`: `CC0-1.0`, `Apache-2.0`, `MIT`, `MPL-2.0`,
`GPL-2.0-only`, `GPL-3.0-only`, `GPL-3.0-or-later`, `LGPL-2.1-only`,
`LGPL-3.0-only`, `BSD-2-Clause`, `BSD-3-Clause`, `EPL-2.0`, `Other`, `None`.

Source files use free-form names. The most common are `BSD-3-Clause` (1,949),
`Other` (1,436), `MIT` (1,169), `Apache-2.0` (472), `CC0-1.0` (384),
`BSD-2-Clause` (339), `GPL-3.0` (255), and `GPL-2.0` (186). Examples of how
other names are mapped:

| Source name | `gov-code.json` |
| :-- | :-- |
| `GPL-3.0`, `GPL.v3`, `gpl3` | `GPL-3.0-only` |
| `GPL-2.0`, `gpl2` | `GPL-2.0-only` |
| `LGPL-2.1`, `LGPL-3.0` | `LGPL-2.1-only`, `LGPL-3.0-only` |
| `Apache License 2.0`, `Apache` | `Apache-2.0` |
| `MIT License` | `MIT` |
| `CC0`, `Public Domain` | `CC0-1.0` |
| `AGPL-3.0`, `The Unlicense`, `EPL-1.0`, `NSF`, `GPL-2.1` | `Other` |
| `NOASSERTION` | Dropped |
| Anything unrecognized | `Other` |

The complete mapping is `LICENSE_MAP` in
[`scripts/utils/normalize.py`](../scripts/utils/normalize.py).

### `vcs`

`git`, `hg`, `svn`, `rcs`, `bzr`, `none`. In the source data, 6,799 records use
`git`, 1,245 omit the field or leave it empty, and 1 uses the invalid value
`zip`.

### `repositoryVisibility`

`public`, `private`.

### `maintenance`

| Value | Meaning |
| :-- | :-- |
| `internal` | Maintained by agency staff. |
| `contract` | Maintained by contractors. |
| `community` | Maintained by an open source community. |
| `none` | Not actively maintained. |

### `agency`

The agency index schema accepts these Clinger-Cohen Act agency acronyms, as
defined by the United States Government Manual: `USDA`, `DOC`, `DOD`, `ED`,
`DOE`, `HHS`, `HUD`, `DHS`, `DOI`, `DOJ`, `DOL`, `DOS`, `DOT`, `TREASURY`, `VA`,
`CFPB`, `EPA`, `FEC`, `GSA`, `NARA`, `NASA`, `NRC`, `NSF`, `OPM`, `SBA`, `SSA`,
`USAID`. An agency directory must match one of these (case-insensitive) to be
included in `gov-code.json`.
