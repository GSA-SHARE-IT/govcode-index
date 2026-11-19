# Normalization Rules

## **STRUCTURAL NORMALIZATION RULES (Stage 3a)**

_Fixes the SHAPE of records: renames, hoists, strips extra keys, coerces types, trims strings, handles empty values_

### **Key-Level Transformations**

**1. Legacy Key Renames** (`rename_top_level`)

- `repository` → `repositoryURL`
- `homepage` → `homepageURL`
- `id` → `identifier`
- Conflict handling: Keep schema key if it exists and isn't empty

**2. Nested Key Renames** (`rename_updated`)

- `updated` (top-level) → `date.lastModified`
- Creates `date` object if needed
- Schema key wins on conflict

**Nested aliases** (`rename_nested_keys`)

- `permissions.license` → `permissions.licenses`
- `date.metaDataLastUpdated` → `date.metadataLastUpdated`
- Runs in Stage 3a before permissions/date cleanup strips unrecognized keys.
- Moves the entire value without changing its contents; subsequent structural
  and value normalization handle license arrays, license values, and timestamps.
- If the canonical key is absent, null, or an empty/whitespace-only string,
  use the alias value. An empty `licenses` array also accepts the alias value.
- Otherwise keep the canonical value; do not merge competing values.
- Remove the alias in either case. Log successful renames as
  `renamed:<parent>.<old>-><parent>.<new>` and conflicts as
  `dropped_legacy_key_conflict:<parent>.<old>`.
- Missing or non-object parent containers are left to existing cleanup and
  validation rules; no container is created by these renames.

**3. Field Hoisting** (`hoist_exemption_text`)

- `exemptionText` (top-level) → `permissions.exemptionText`
- Creates `permissions` object if needed
- Schema key wins on conflict

**4. Legacy Usage Fields Removal** (`struct_drop_legacy_usage_fields`)

- Removes top-level `openSourceProject` and `governmentWideReuseProject` whenever
  present, regardless of their values or the source agency.
- Logs each removal as `dropped_legacy_field:<field>`.
- Does not create or modify `permissions` or `permissions.usageType`.
- Existing independent usage-type normalization rules remain unchanged.

---

### **Nested English Description** (`struct_flatten_description`)

- Runs before optional-string cleanup in Stage 3a.
- For an object containing `description.en.shortDescription` or
  `description.en.longDescription`:
  - Replace `description` with the English `shortDescription`.
  - Hoist the English `longDescription` to top-level `longDescription`.
  - Keep an existing nonempty top-level `longDescription` on conflict.
  - If `shortDescription` is absent, omit `description`.
  - Replacing the nested object removes its other keys and language variants.
- Existing string descriptions remain unchanged by this transformation.
- Missing/non-object `en`, or `en` without either recognized key: leave the
  description unchanged and log `skipped_flatten:description(no recognized English description)`.
- Log successful moves as `renamed:description.en.shortDescription->description`
  and `hoisted:description.en.longDescription->longDescription`; log conflicts as
  `dropped_legacy_key_conflict:description.en.longDescription` and a missing short
  description as `omitted_missing:description.en.shortDescription`.
- Both output fields then receive optional-string cleanup: trim strings and
  omit empty strings/nulls; log and preserve unexpected non-string values.

---

### **Required String Fields** (`struct_clean_required_strings`)

_Fields: name, identifier, organization, status, repositoryURL, repositoryVisibility, maintenance, feedbackMechanism_

- **String values:**
  - Trim whitespace (both ends)
  - Empty string → null

- **Non-string values (Coercion):** ⭐ _Enhanced_
  - Coerce to string using `str(value)`
  - Trim whitespace after coercion
  - Empty result after coercion → null
  - Coercion failure → null
  - Examples:
    - Numeric identifier `2294` (int) → `"2294"` (string)
    - Non-numeric types → attempted coercion with logging

---

### **Optional String Fields** (`struct_clean_optional_strings`)

_Fields: description, longDescription, homepageURL, downloadURL, disclaimerURL, disclaimerText, vcs, SBOM, AIUseCaseID_

- **Trim whitespace**
- **Empty string/null → omit field** (delete key)
- **Non-string values**: Log unexpected type, leave unchanged

---

### **Version Field** (`struct_clean_version`)

- **Number types → string** (coerce int/float to string)
- **Trim whitespace** if string
- **Empty string/null → omit**
- **Bool type**: Log unexpected, omit
- **Other types**: Log unexpected, omit

---

### **Permissions Object** (`struct_clean_permissions`)

**Permissions structure:**

- Strip unrecognized keys (keep only: `licenses`, `usageType`, `exemptionText`)
- **`licenses` array:**
  - Null → empty list
  - Single object → wrap in list
  - Each item: strip to `{name, URL}` only
  - Empty values → null
  - Drop completely empty items

- **`usageType` array:**
  - Null → empty list
  - Ensure list type, trim strings

- **`exemptionText` field:**
  - Trim whitespace
  - Empty → null

---

### **Reuse Frequency** (`struct_clean_reuse_frequency`)

_Object with optional fields: forks, clones, downloads_

- **Coerce to integers** (from strings/floats)
- **Empty/null values → omit**
- **Non-numeric → omit**

---

### **Labor Hours** (`struct_clean_labor_hours`)

- **Coerce to number** (int or float, from strings)
- **Empty/null/non-numeric → omit**

---

### **Contract Numbers** (`struct_clean_contract_number`)

- Single string or number → wrap in an array.
- Convert numeric values (integers/floats) to strings, including inside arrays.
- Trim strings; preserve identifier formatting such as leading zeros and do not
  split strings on punctuation.
- Drop empty/whitespace-only strings and null array elements.
- Drop unsupported values (including booleans, objects, and nested arrays),
  logging `dropped_unexpected_type:contractNumber`; do not stringify them.
- Keep an empty result as `[]`. Missing or null fields remain unchanged for the
  validation fill stage to supply `[]`.
- Log wrapping, coercion, trimming, and empty-item removal as
  `wrapped_in_list:contractNumber`, `coerced_to_string:contractNumber`,
  `trimmed:contractNumber`, and `dropped_empty_item:contractNumber`.
- Preserve order and duplicates in Stage 3a; existing Stage 3b rules deduplicate.

---

### **String Lists** (`struct_clean_string_lists`)

**Languages array:**

- Null → omit field
- Ensure array type
- Trim strings, remove empty items
- **Drop "None" string literals** (indicates no programming languages)
- Empty result → omit

**Tags array:**

- Null → omit field
- Ensure array type
- Trim strings, remove empty items

---

### **Object Lists** (`struct_clean_object_list`)

_Applied to: relatedCode, reusedCode, partners_

**For each object in list:**

- Strip to allowed keys only:
  - `relatedCode` / `reusedCode`: `{name, URL}`
  - `partners`: `{name, email}`

- **Trim string fields** (by allowed key)
- **Keep isGovernmentRepo** as boolean (if present in relatedCode)
- **Drop non-object items**
- **Drop completely empty items** (all allowed fields empty)

**List handling:**

- Single object → wrap in array
- Non-array type → log unexpected, skip
- Empty result → omit field

---

### **Date Object** (`struct_clean_date`)

_Object with optional fields: created, lastModified, metadataLastUpdated_

- **Null or empty array → omit entire date field**, logging `omitted_empty:date`
- **Nonempty arrays containing only nulls or empty/whitespace-only strings → omit
  the entire date field**, logging `omitted_placeholder_array:date`.
  Examples: `[""]`, `[null]`, `["", null, "  "]`. No timestamp is inferred.
- **Other non-object types → log `unexpected_type:date`, leave unchanged** for
  validation to report. This includes arrays with any nonblank string, object,
  nested array, number, or boolean, even if other items are empty placeholders.
- Strip unrecognized keys (keep only: `created`, `lastModified`, `metadataLastUpdated`)
- **Trim string fields**
- **Empty values → omit field key**
- **Empty object → omit entire date field**

---

### **Contact Object** (`struct_clean_contact`)

_Object with optional fields: email, name_

- Strip unrecognized keys (keep only: `email`, `name`)
- **Trim string fields**
- **Empty values → delete key**
- **Non-object type → log unexpected, skip**
- **Empty object → omit entire contact field**

---

### **Strip Extra Keys**

Applied throughout: Keep only schema-defined keys in nested objects

---

---

## **VALUE NORMALIZATION RULES (Stage 3b)**

_Normalizes VALUES: validates, maps to enums, parses formats, canonicalizes_

### **URL Parsing** (`parse_url`) ⭐ _Enhanced_

**URL validation and normalization helper:**

- **Scheme requirement**: URLs must have a scheme (http, https, etc.)
- **Automatic HTTPS prefix fallback:** ⭐ _New_
  - If URL lacks a scheme but has a netloc (e.g., `www.apache.org/licenses/LICENSE-2.0`)
  - Automatically prepends `https://` and re-parses
  - Examples:
    - Input: `"www.apache.org/licenses/LICENSE-2.0"` → `"https://www.apache.org/licenses/LICENSE-2.0"`
    - Input: `"github.com/user/repo"` → `"https://github.com/user/repo"`
- **Invalid URLs remain invalid**
  - URLs with invalid characters or structure are still rejected
  - Whitespace in URLs causes rejection

---

### **Repository URL** (`value_clean_repository_url`)

- **GitHub Git protocol → HTTPS:** Convert a `git://github.com/` prefix to
  `https://github.com/` (scheme and host matching is case-insensitive), logging
  `github_git_to_https:repositoryURL`. Match the actual URL scheme and exact
  authority, not text embedded in a path/query or another host. Other Git hosts
  are unchanged. Existing `.git`/trailing-slash cleanup then applies, allowing
  the filling stage's existing GitHub feedback inference to recognize the URL.
- **Special case**: String "private" → keep as-is
- **Invalid URL → null**
  - Now includes URLs without scheme (unless https:// prefix fallback succeeds)
  - Examples:
    - `"www.example.com/licenses/LICENSE-2.0"` → `"https://www.example.com/licenses/LICENSE-2.0"` ✓ (via parse_url fallback)
    - `"not a url"` → null
- **Bare domain** (just domain, no path):
  - Move to `homepageURL` (if empty)
  - Set `repositoryURL` to null
- **Valid URL:**
  - **Canonicalize:**
    - Lowercase scheme and netloc
    - Remove trailing `.git` from path
    - Remove trailing slashes
  - Upgrade to HTTPS if applicable

---

### **Status** (`value_clean_status`)

**Mapping (case-insensitive):**

- `ideation` → `Ideation`
- `development` → `Development`
- `alpha` → `Alpha`
- `beta` → `Beta`
- `release-candidate` / `release candidate` / `rc` → `Release Candidate`
- `production` → `Production`
- `archival` → `Archival`

**Unmapped values:**

- Check if starts with known prefix (`alpha`, `beta`, `release candidate`)
- If no match → set to null
- Recognized by exact match in enum: keep as-is

---

### **Dates** (`value_clean_dates`)

_Fields: created, lastModified, metadataLastUpdated_

**Date parsing (in order):**

1. Try YYYY/MM/DD format → convert to YYYY-MM-DD
2. Try ISO 8601 format (with optional time and timezone)
3. Try text formats: `%B %d, %Y` / `%b %d, %Y` / `%d %B %Y` / `%d %b %Y`

**Output format:** RFC 3339 string

- Date-only → `YYYY-MM-DDTHH:MM:SSZ` (assume 00:00:00 UTC)
- With time → preserve, normalize timezone to ±HH:MM or Z
- Invalid → omit field

**Flags logged:**

- `date_only`: No time component provided
- `added_seconds`: Seconds inferred as 00
- `assumed_utc`: No timezone provided, assumed UTC

---

### **Licenses** (`value_clean_licenses`)

_Inside permissions.licenses array_

**Per license object:**

1. **Drop if no `name` field**
2. **Map `name` to enum:**
   - Direct match in enum → keep
   - Match in LICENSE_MAP after collapsing whitespace and lowercasing → map
   - `CC0 1.0 Universal` → `CC0-1.0`, including case and whitespace variants;
     log `license_mapped`. The license URL continues through existing URL cleanup.
   - Unrecognized → `Other`
   - Special case `noassertion` → drop entire license
3. **Validate URL field** (via `value_clean_url_field`)
4. **Drop completely empty items**
5. **Deduplicate** in result list

**License enum includes:** MIT, Apache-2.0, GPL-2.0-only, GPL-3.0-only, GPL-3.0-or-later, LGPL-2.1-only, LGPL-3.0-only, BSD-2-Clause, BSD-3-Clause, MPL-2.0, EPL-2.0, CC0-1.0, Other, None

---

### **Usage Type** (`value_clean_usage_type`)

_Inside permissions.usageType array_

**Per usage value:**

1. **Case-insensitive fuzzy match** to enum
2. **Recognized values kept** (recased to canonical form):
   - `openSource`, `governmentWideReuse`, `exemptByNationalSecurity`, etc.
3. **Legacy values kept verbatim** (marked as legacy):
   - `exemptByAgencySystem`, `exemptByAgencyMission`, `exemptByLaw`
4. **Unrecognized values → drop**
5. **Deduplicate** in result

---

### **Tags** (`value_clean_tags_and_lists`)

**Tags normalization:**

- **Normalize each tag**: Remove extra whitespace, lowercase
- **Drop empty tags**
- **Deduplicate** (preserve order, first occurrence kept)

**Languages & contractNumber (if lists):**

- **Deduplicate** (keep order)

---

### **Labor Hours** (`value_clean_labor_hours`)

**Value validation:**

- **Zero → omit field**
- **Negative → omit field**
- **Bool type → skip (don't process)**
- **Valid number → keep**

---

### **Contact Email** (`value_clean_contact_email`)

**Email validation:**

- **Valid format** (simple regex: `^[^@\s]+@[^@\s]+\.[^@\s]+$`): Keep
- **Malformed → null**

---

### **Enum Fields** (`value_clean_enum`)

_Applied to: vcs, repositoryVisibility, maintenance_

**Per field:**

- **Non-string values → skip**
- **Lowercase match to enum:**
  - If matches → lowercase the value
  - If no match:
    - **Required field** → set to null
    - **Optional field** → omit field

**Enum values:**

- **vcs**: `git`, `hg`, `svn`, `rcs`, `bzr`, `none`
- **repositoryVisibility** (required): `public`, `private`
- **maintenance** (required): `internal`, `contract`, `community`, `none`

---

### **URL Fields** (`value_clean_url_field`)

_Applied to: homepageURL, downloadURL, disclaimerURL, feedbackMechanism_

**Per URL:**

- **Automatic HTTPS prefix fallback:** ⭐ _Enhanced_
  - URLs without scheme (e.g., `www.apache.org/...`) automatically get `https://` prepended
  - Prevents valid URLs from becoming null
  - Examples:
    - `"www.apache.org/licenses/LICENSE-2.0"` → `"https://www.apache.org/licenses/LICENSE-2.0"` ✓
    - License URLs in nested objects now preserved
- **Upgrade to HTTPS** if applicable (HTTP → HTTPS, same host/path)
- **Canonicalize** (lowercase scheme and netloc, trim path)
- **Invalid → null** (only after fallback attempt fails)
- **Required field (feedbackMechanism) → must have valid URL or null**
- **Optional fields → omit if null/empty**

---

## **Summary of Transformations**

| **Stage**          | **Purpose**       | **Key Operations**                                                                               |
| ------------------ | ----------------- | ------------------------------------------------------------------------------------------------ |
| **3a: Structural** | Fix record shape  | Rename keys, hoist fields, strip extras, **coerce types** ⭐, trim strings, handle empties       |
| **3b: Value**      | Normalize content | Map to enums, parse dates, **canonicalize URLs with fallback** ⭐, validate formats, deduplicate |

Both stages are **idempotent**: running twice produces the same result as running once.

---

### **Integration with Validation Layer**

These enhancements work together with the new validation module (`scripts/utils/validate.py`) to ensure:

- All required fields are present (even if filled with defaults)
- All fields have correct types (strings are strings, etc.)
- URLs are valid and usable
- Legacy numeric IDs are properly formatted
- Languages arrays contain only actual programming language values

## CMS metadata and structural normalization

These rules are implemented in [`scripts/utils/normalize.py`](../scripts/utils/normalize.py).
They apply to recognized fields that are present, regardless of agency, and do
not change organizational identity. Source inventory files remain untouched.
CMS field cleanup runs after the existing structural and value stages.

Definitions come from the pinned
[CMS 2.2.0 schema](../scripts/schemas/cms-2.2.0.json), downloaded from the
[official schema source](https://gsa-share-it.github.io/codejson-schemas/schemas/cms/schema-2.2.0.json).

### CMS field types and values

| Fields | Normalization | Example |
| :-- | :-- | :-- |
| `localisation`, `userInput`, `relatedCode[].isGovernmentRepo` | Trim strings and convert case-insensitive `true`/`yes` and `false`/`no` to booleans. Preserve actual booleans. | `"No"` → `false` |
| `maturityModelTier` | Convert integer strings to integers. Preserve zero; do not round floats or convert booleans. Values outside 0–4 remain available for validation. | `"0"` → `0` |
| `repositoryType`, `repositoryHost`, `softwareType`, `fismaLevel` | Trim strings and map case-insensitive enum matches to the exact schema spelling. Preserve unrecognized values. | `"apis"` → `"APIs"`; `"Low"` → `"low"` |
| `platforms`, `categories`, `projects`, `systems`, `subsetInHealthcare`, `userType` | Wrap scalar strings in arrays, trim string items, remove blank/null items, and deduplicate in source order. | `"Government"` → `["government"]` for `userType` |
| `platforms`, `subsetInHealthcare`, `userType` | Normalize enum spelling; split comma-packed items only when every token matches the enum. | `["windows,mac,linux"]` → `["windows", "mac", "linux"]` |
| `userType` | Correct the explicitly recognized typo `Governemnt`. | `["Governemnt"]` → `["government"]` |
| `group` | Trim strings and unwrap an array containing one string. Preserve ambiguous multi-item arrays. | `["CMS/CMMI"]` → `"CMS/CMMI"` |
| `longDescription` | Trim strings; structural description cleanup below handles blanks and unsupported types. Do not generate or pad text to meet length limits. | `" Text "` → `"Text"` |

Canonical spelling preserves `APIs`, `SNAP`, `TANF`, and `configurationFiles`.
`categories`, `projects`, and `systems` have no item enum in this schema; their
values are not automatically lowercased or split on commas.

Missing CMS extension fields are not added. Unknown enum values, unsupported
list items, and malformed CMS extension types are retained for review rather
than guessed. Changed fields record `normalized_cms_field:<field>` in the
normalization context.

No new alias mappings are applied to `repoType`, `feedbackMechanisms`, `upstream`,
or `projectURL`; these extension properties remain unchanged. Existing cleanup
preserves the string sentinels `AIUseCaseID: "0"` and `SBOM: "None"`.

### Contract numbers (`struct_clean_contract_number`)

- Convert a scalar string or number to an array of strings.
- Convert numeric array items to strings, including zero. Preserve leading
  zeros already present in strings and do not split identifiers on punctuation.
- Trim strings, remove blanks/nulls, and deduplicate while retaining order.
- Convert a null field to `[]`. A missing field stays absent until filling.
- Drop unsupported items, including booleans, objects, and nested arrays, with
  `dropped_unexpected_type:contractNumber` recorded in the context.
- Record changed values with `normalized:contractNumber`.

Example: `[0, "0", " 00123 ", null, ""]` → `["0", "00123"]`.

### Flat descriptions (`struct_flatten_description`)

- Move `description.en.shortDescription` to string `description`.
- Move `description.en.longDescription` to top-level `longDescription`.
- Also recognize direct `description.shortDescription` and
  `description.longDescription` when no `en` key is present.
- Keep an existing nonblank top-level `longDescription` on conflict and record
  `description_long_conflict_kept_top_level`.
- Trim both text fields and omit blank/null or unsupported values. Never
  stringify a description object. Missing short text does not prevent retaining
  long text.
- Unrecognized language variants and nested keys are not carried into the flat
  fields; the original source inventory retains them. No text is generated.
- Record flattening with `flattened:description`; unsupported field types record
  `invalid_description_to_null:<field>` before optional-string cleanup omits them.

Example:

```json
{
  "description": {
    "en": {
      "shortDescription": "Short overview",
      "longDescription": "Detailed overview"
    }
  }
}
```

becomes:

```json
{
  "description": "Short overview",
  "longDescription": "Detailed overview"
}
```

### Placeholder dates (`struct_clean_date`)

- Arrays containing only blank strings or nulls become JSON `null`. Examples:
  `[""]`, `[" ", null]`, and `[]`.
- Existing null stays null through repeated normalization and filling.
- Missing dates stay absent. Non-placeholder arrays remain available for
  validation rather than being interpreted as timestamps.
- Existing date-object cleanup is unchanged.
- Record conversion with `placeholder_array_to_null:date`.

### HHS applicability and diagnostics

An HHS record is marked as using CMS-style metadata when its original object
contains any of these fields, even if the value is empty or null:
`localisation`, `repositoryType`, `repositoryHost`, `userInput`, `fismaLevel`,
`group`, `projects`, `systems`, `subsetInHealthcare`, `userType`,
`maturityModelTier`, `platforms`, `categories`, `softwareType`, `longDescription`.

The marker belongs to diagnostics and logs, not the project JSON. Supplied-field
checks run after normalization and before filling. They do not require missing
CMS fields, reject extension keys, or enforce CMS organizational identity.
CMS-specific constraints such as the repository-host enum apply only within
these HHS checks. Null dates are an explicit local exception to the CMS schema.
See [VALIDATION_RULES.md](VALIDATION_RULES.md) for validation details.
