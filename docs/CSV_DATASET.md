# CSV dataset

[`gov_code_to_csv.py`](../scripts/gov_code_to_csv.py) converts the committed
[`gov-code.json`](../gov-code.json) into [`gov-code.csv`](../gov-code.csv).
The export has one row per project and 63 fixed columns. Row counts and file
sizes change with each refresh; the CSV header is not a project record.

## Usage

From the repository root:

```bash
python scripts/gov_code_to_csv.py
```

Default paths are relative to the repository, not the caller's working directory.
For custom paths:

```bash
python scripts/gov_code_to_csv.py /path/to/input.json /path/to/output.csv
```

Custom relative paths are relative to the caller's working directory. The
converter uses only the Python standard library. Use Python 3.13 to match the
repository's workflows. It does not download data or rebuild `gov-code.json`.
The dataset workflow runs consolidation first, then exports and commits the CSV.

## Columns and flattening

`govcode_id` is the first column, followed by `agency`, `name`, and `identifier`.
The exact order is defined by `COLUMN_ORDER` in the script and listed in the
[data dictionary](DATA_DICTIONARY.md). The parent agency is added to each row;
`govcode_id` is copied from the project rather than generated during export.

| JSON fields | CSV representation |
| :-- | :-- |
| Core project strings and URLs | Corresponding named columns |
| `permissions.licenses[]` | Pipe-separated names in `permissions_licenses` and `permissions_licenses_name`, with URLs in `permissions_licenses_URL` |
| `permissions.usageType[]` | Pipe-separated `permissions_usageType` |
| `permissions.exemptionText` | `permissions_exemptionText` |
| `contact.*` | `contact_email`, `contact_name`, `contact_url`, `contact_phone` |
| `date.*` | `date_created`, `date_lastModified`, `date_metadataLastUpdated` |
| `reuseFrequency.*` | `reuseFrequency_forks`, `reuseFrequency_clones`, `reuseFrequency_downloads` |
| `relatedCode[]`, `reusedCode[]` | Combined name/URL pairs and separate name/URL columns; related-code government flags have their own column |
| `partners[]` | Combined name/email pairs and separate `partners_name` and `partners_email` columns |
| `languages[]`, `tags[]`, `contractNumber[]` | Pipe-separated strings |
| CMS extension fields | Columns for long descriptions, grouping, repository metadata, categories, platforms, users, systems, localisation, and maturity metadata |

For example, two related-code objects become
`name1|url1|name2|url2` in `relatedCode`. Separate columns expose the names,
URLs, and available government-repository flags. Blank components preserve
alignment where the converter retains an object.

## Values and formatting

- UTF-8, comma-delimited output uses Python's `csv.DictWriter` with double-quote
  escaping and its default CRLF row endings.
- Missing or null values become empty cells. Empty arrays and objects produce
  empty values in their flattened fields.
- Numeric zero is preserved in labor hours and reuse counters.
- String normalization replaces newlines and tabs with spaces, trims surrounding
  whitespace, and collapses repeated spaces.
- Boolean values become `true` or `false`.
- Import identifiers and contract numbers as text in spreadsheet applications
  to preserve leading zeros already present in strings.
- Standalone export leaves the `govcode_id` cell blank if the input lacks it;
  normal dataset publication relies on consolidation to reject missing IDs.

## Limitations

CSV contains only the configured columns, not every unknown or nested JSON
field. Flattening is not reversible: arrays use `|` without separate escaping
for literal pipe characters, and string whitespace is normalized. Use the JSON
for full normalized records and the source snapshots for original metadata.

CSV row totals reflect the input dataset. A successful export does not verify
source completeness, ID uniqueness, or remote-schema compliance; those checks
and limitations belong to collection and consolidation.
