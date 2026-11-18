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

**3. Field Hoisting** (`hoist_exemption_text`)

- `exemptionText` (top-level) → `permissions.exemptionText`
- Creates `permissions` object if needed
- Schema key wins on conflict

**4. Legacy Usage Fields Migration** (`struct_migrate_legacy_usage_fields`)

- Migrates legacy boolean project-type fields to `permissions.usageType`
- **openSourceProject:**
  - If value is `1` or `"1"` → adds `"openSource"` to `permissions.usageType`
  - Any other value → field is dropped
- **governmentWideReuseProject:**
  - If value is `1` or `"1"` → adds `"governmentWideReuse"` to `permissions.usageType`
  - Any other value → field is dropped
- **Behavior:**
  - Both legacy fields are removed from the record after processing
  - Creates `permissions` object if needed
  - Adds to existing `usageType` array (doesn't replace)
  - Avoids duplicates in `usageType`
  - If neither field equals 1, `permissions` object is not created

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

_Fields: description, homepageURL, downloadURL, disclaimerURL, disclaimerText, vcs, SBOM, AIUseCaseID_

- **Trim whitespace**
- **Empty string/null → omit field** (delete key)
- **Non-string values**: Log unexpected type, delete field

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
   - Case-insensitive fuzzy match in LICENSE_MAP → map
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
