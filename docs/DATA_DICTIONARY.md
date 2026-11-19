# Data Dictionary

This document defines every field found in the data, at three levels:

- **Source files** (`agency-indexes/`) are stored exactly as agencies publish
  them. Agencies publish the code.gov **code.json 2.0.0** metadata format, with
  some legacy and non-standard keys.
- **`gov-code.json`** targets the
  [**code.json 0.1.0** project schema](https://gsa-share-it.github.io/codejson-schemas/schemas/schema-0.1.0.json)
  inside the
  [agency index schema 1.0.0](https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json).
  It adds several required fields that 2.0.0 does not have.

- **`gov-code.csv`** is the flattened export of `gov-code.json`, with one row
  per project and 62 columns, including CMS fields and separate object subfields.

**How to read the tables:**

- **Req.** ✔ means the field is required by the 0.1.0 schema. `fill_record`
  always includes required fields in `gov-code.json`, using `null`, `[]`, or `{}`
  when no value can be derived.
- **Source fill** is the share of the 8,045 project files under
  `agency-indexes/` where the field is present and not empty, as of the
  2026-11-18 refresh. These percentages are historical, not measurements of the current dataset.
  "New" describes the older inventory snapshot; public collections now supply
  some of these fields. Current CSV coverage is reported separately below.

## Contents

- [Agency index object](#agency-index-object)
- [Project record](#project-record)
- [How `gov-code.json` changes each field](#how-gov-codejson-changes-each-field)
- [Legacy and non-standard keys in source data](#legacy-and-non-standard-keys-in-source-data)
- [Enumerations](#enumerations)
- [CMS fields and CSV columns](#cms-fields-and-csv-columns)
- [CSV review snapshot](#csv-review-snapshot)

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
| `date` | object or null | | Dates describing the release. | 98% |
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

These fields were introduced in 0.1.0. Some current public project records
supply them; they are no longer universally absent from source data.

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
| Recognized string fields | Leading and trailing whitespace is trimmed. An empty optional string is removed. An empty required string becomes `null`. |
| `identifier` | Legacy `id` is renamed. Otherwise the value is derived from `repositoryURL` as lower-case `host/path` (for example `github.com/cisagov/acid`). Without a usable URL it becomes `{agency}:{name-slug}-{first 8 hex chars of SHA-1}`. |
| `organization` | Missing values are filled with the agency acronym. |
| `version` | Numbers are converted to strings. Empty or `null` values are removed. |
| `status` | Known spellings are mapped to the enum, for example `rc` → `Release Candidate` and `Alpha v0.11 (Prototype)` → `Alpha`. Unmappable values become `null`. Missing values are never guessed. |
| `maintenance` | Lower-cased if valid, otherwise `null`. Missing values are never guessed; supplied valid values are retained. |
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

## CMS fields and CSV columns

The exporter is [`scripts/gov_code_to_csv.py`](../scripts/gov_code_to_csv.py).
Run `python3 scripts/gov_code_to_csv.py` to write `gov-code.csv`; optional
positional arguments select the input and output files. All columns are emitted
for every agency. CMS-style classification controls validation, not export.
It does not establish that a record belongs to CMS.

### Added columns

Names below are the exact CSV headers. Unqualified source paths are top-level
project properties. These 26 fields supplement the original export. `agency` comes first, followed by the 44 columns in
our requested project-field order; remaining columns follow `AIUseCaseID`.
Nested paths use underscore headers (for example, `date.created` becomes
`date_created`). Separate subfield columns have also been added:
`permissions_licenses_name`, `relatedCode_name`, `relatedCode_URL`,
`reusedCode_name`, `reusedCode_URL`, `partners_name`, and `partners_email`.
Each is pipe-separated and retains empty positions to align with sibling fields.
`permissions_licenses_name` intentionally duplicates `permissions_licenses`,
which retains its existing license-name representation. Existing combined
related/reused-code and partner columns retain alternating member pairs.

### CSV header order

```text
1. agency
2. name
3. identifier
4. version
5. description
6. organization
7. status
8. permissions_licenses
9. permissions_licenses_name
10. permissions_licenses_URL
11. permissions_usageType
12. permissions_exemptionText
13. reuseFrequency_forks
14. reuseFrequency_clones
15. reuseFrequency_downloads
16. repositoryURL
17. repositoryVisibility
18. homepageURL
19. downloadURL
20. disclaimerURL
21. disclaimerText
22. vcs
23. laborHours
24. languages
25. maintenance
26. contractNumber
27. SBOM
28. relatedCode
29. relatedCode_name
30. relatedCode_URL
31. relatedCode_isGovernmentRepo
32. reusedCode
33. reusedCode_name
34. reusedCode_URL
35. partners
36. partners_name
37. partners_email
38. date_created
39. date_lastModified
40. date_metadataLastUpdated
41. tags
42. contact_email
43. contact_name
44. feedbackMechanism
45. AIUseCaseID
46. contact_url
47. contact_phone
48. longDescription
49. group
50. repositoryHost
51. repositoryType
52. softwareType
53. fismaLevel
54. platforms
55. categories
56. userType
57. subsetInHealthcare
58. projects
59. systems
60. localisation
61. userInput
62. maturityModelTier
```


| CSV column / source path | JSON type | Meaning and CSV representation |
| :-- | :-- | :-- |
| `version` | string | Software release version, not the parent agency-index schema version. |
| `longDescription` | string | Extended project description; CMS expects 150–10,000 characters. Short supplied text is still exported. |
| `maintenance` | string | Maintenance arrangement: `internal`, `contract`, `community`, or `none`. |
| `group` | string | Associated department, organization, or group; distinct from owning `organization`. |
| `repositoryHost` | string | Source hosting location/organization label; not necessarily a URL. CMS uses a restricted vocabulary. |
| `repositoryType` | string | Repository purpose: `package`, `website`, `standards`, `libraries`, `data`, `application`, `tools`, or `APIs`. |
| `softwareType` | string | `standalone/mobile`, `standalone/iot`, `standalone/desktop`, `standalone/web`, `standalone/backend`, `standalone/other`, `addon`, `library`, or `configurationFiles`. |
| `fismaLevel` | string | Supplied security categorization: `low`, `moderate`, or `high`. No category is inferred. |
| `SBOM` | string | SBOM/dependency link or literal `None`; the sentinel is not an empty cell. |
| `AIUseCaseID` | string | AI inventory identifier; literal `0` means not listed and is preserved. |
| `disclaimerText` | string | Disclaimer text. |
| `disclaimerURL` | string | Link to disclaimer language. |
| `platforms` | string array | Supported platforms, joined with pipes: `web`, `windows`, `mac`, `linux`, `ios`, `android`, `other`. |
| `categories` | string array | Project categories, pipe-separated. The CMS schema does not enforce an item enum. |
| `userType` | string array | `providers`, `patients`, `government`, `applicants`, `beneficiaries`, `enrollees`; pipe-separated. |
| `subsetInHealthcare` | string array | `policy`, `operational`, `medicare`, `medicaid`, `SNAP`, `TANF`, `human-benefit-services`; pipe-separated. |
| `projects` | string array | Related project names or supplied references, pipe-separated. |
| `systems` | string array | Systems the project interfaces with or depends on, pipe-separated. |
| `localisation` | boolean | Whether multiple languages are supported; lowercase `true` or `false`. |
| `userInput` | boolean | Whether the software accepts user input; lowercase `true` or `false`. |
| `maturityModelTier` | integer | CMS maturity tier 0–4. Zero is a populated value. |
| `partners` | object array | Alternating agency-name/email values: `HHS\|person@example.org\|CDC\|`. Missing members retain empty positions. |
| `date_metadataLastUpdated` ← `date.metadataLastUpdated` | date-time string | Metadata update timestamp, separate from project modification time. Null `date` exports as blank. |
| `permissions_exemptionText` ← `permissions.exemptionText` | string or null | Supplied explanation of a usage exemption. |
| `permissions_licenses_URL` ← `permissions.licenses[].URL` | string array | Pipe-separated license links, positionally aligned with `permissions_licenses`; missing links retain empty positions. |
| `relatedCode_isGovernmentRepo` ← `relatedCode[].isGovernmentRepo` | boolean array | One pipe-separated `true`/`false`/blank value per exported related-code object, aligned with its name/URL pair. |

Allowed values describe expectations, not guarantees: invalid supplied values
can survive non-blocking validation and are exported unchanged. See
[NORMALIZATION_RULES.md](NORMALIZATION_RULES.md) and
[VALIDATION_RULES.md](VALIDATION_RULES.md) for CMS applicability and cleanup.

### Original column mappings

| CSV columns | Source and representation |
| :-- | :-- |
| `agency` | Parent agency index's acronym, repeated for each project. |
| `name`, `identifier`, `organization`, `status`, `repositoryURL`, `repositoryVisibility`, `feedbackMechanism`, `downloadURL`, `homepageURL`, `vcs`, `description` | Corresponding top-level project strings. |
| `laborHours` | Top-level number; zero is preserved if present in JSON. Existing consolidation can omit zero before export. |
| `permissions_licenses` | License names in array order; empty positions align with the license URL column. |
| `permissions_usageType` | `permissions.usageType`, pipe-separated. |
| `contact_email`, `contact_name`, `contact_url`, `contact_phone` | `contact.email`, `contact.name`, `contact.URL`, `contact.phone`. The last two are normally removed during consolidation. |
| `date_created`, `date_lastModified` | `date.created` and `date.lastModified`. |
| `reuseFrequency_forks`, `reuseFrequency_clones`, `reuseFrequency_downloads` | Corresponding nested counts; numeric zero is preserved. |
| `relatedCode`, `reusedCode` | Alternating name/URL pairs from each object, pipe-separated. Related-code entries containing only a government flag retain an empty name/URL pair. |
| `languages`, `tags`, `contractNumber` | Corresponding string arrays, pipe-separated. Contract identifier strings retain leading zeros. |

### Serialization and limitations

- Missing/null scalar values and empty arrays become blank CSV cells. CSV does
  not distinguish those forms of missingness. Actual false and zero values are
  retained; they are not treated as missing.
- Text newlines and tabs become spaces and repeated spaces are collapsed.
  CSV quoting handles commas and double quotes; the file uses UTF-8.
- Pipes delimit arrays and object-member pairs. Literal pipes inside members
  are not escaped, so the flattened representation is not losslessly reversible.
  Use JSON when exact structure or original whitespace matters.
- Open CSV files with identifier/contract columns configured as text to prevent
  spreadsheet software from converting numeric-looking strings or stripping zeros.
- Unknown extension properties such as `repoType`, `feedbackMechanisms`,
  `upstream`, and `projectURL` are not additional CSV columns.
- Export does not deduplicate records or resolve source validation findings.

## CSV review snapshot

Reviewed on 2026-11-19 against the local `gov-code.json`, before the later
column-order change and seven separate subfield additions (55 columns then,
62 in the current exporter). These counts describe
this generated snapshot and will change after refreshes; they are not live
source availability checks.

- 9,430 rows across 11 agencies; 55 unique column names.
- Every row matches the current export transformation of the corresponding JSON
  project, with no row-count, cell-value, or row-width discrepancies.
- 93 HHS records are CMS-style. All have boolean `localisation` and `userInput`,
  and integer maturity tiers 0–4. CSV contains 87 `false`/6 `true` localisation
  values, 57 `false`/36 `true` user-input values, and eight maturity-tier zeros.
- 69 of those 93 records have no supplied-field CMS findings. Remaining findings
  include 18 short long descriptions, seven repository-host values and seven
  repository-type values outside the vocabulary, three blank software types,
  three null statuses, two blank FISMA levels, and one record each with platform,
  maintenance, or license-URL findings. Counts overlap across records.
- Four columns are entirely blank: `contact_url`, `contact_phone`,
  `reuseFrequency_downloads`, and `partners`. Blank contact URL/phone columns
  reflect existing consolidation rules, not an exporter failure.
- There are 176 repeated `(agency, identifier)` groups, all in DOE, accounting
  for 712 rows beyond the first occurrence per group. This is not proof that
  entire records are duplicates; identifiers should not be assumed unique.
- No literal pipe was found in a top-level string-array member in this snapshot.
  The serialization ambiguity remains a format limitation for future values.

Selected populated-cell counts (false and zero count as populated):

| Column | Entire CSV | CMS-style HHS rows |
| :-- | --: | --: |
| `longDescription` | 93 | 88 |
| `maintenance` | 109 | 92 |
| `repositoryHost` | 94 | 91 |
| `repositoryType` | 92 | 88 |
| `SBOM` | 78 | 67 |
| `AIUseCaseID` | 82 | 67 |
| `projects` | 53 | 49 |
| `systems` | 5 | 5 |
| `date_metadataLastUpdated` | 7,407 | 87 |
| `permissions_exemptionText` | 393 | 0 |
| `permissions_licenses_URL` | 7,187 | 91 |
| `relatedCode_isGovernmentRepo` | 7 | 2 |

A populated cell is not necessarily valid or informative: a short placeholder
description, `SBOM: None`, and `AIUseCaseID: 0` each count as populated.
