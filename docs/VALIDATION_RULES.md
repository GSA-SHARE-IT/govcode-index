# Validation Rules

## Overview

Validation is a two-stage pipeline applied after normalization:

1. **Stage 1: Validate** (`validate_record`)
   - Checks required fields are present
   - Validates data types
   - Performs soft format checks (warnings only, don't block)
   - Soft enum validation (warnings for unrecognized values)
   - **Returns:** `is_valid=True` regardless, plus `errors[]` and `warnings[]`

2. **Stage 2: Fill & Standardize** (`fill_record`)
   - Fills missing required fields with derived/inferred values
   - Standardizes enum values where mappings exist
   - Preserves original values when standardization not possible
   - Tracks all changes in a derivation dictionary
   - **Returns:** `(filled_record, derivation_dict)`

Target schema: **code.json 0.1.0** (government-wide generic schema)  
Preserves non-standard values when standardization is not possible.

---

## **STAGE 1: VALIDATION** (`validate_record`)

### **Required Fields (All Must Be Present)**

```
name, identifier, organization, status,
permissions, reuseFrequency, repositoryURL,
repositoryVisibility, maintenance, contractNumber,
contact, feedbackMechanism
```

If any required field is missing → **ERROR**

---

### **Type Validation**

#### **Record Container**

- Must be a JSON object (dict)
- Non-object type → **ERROR:** "Record must be a JSON object, got {type}"

#### **String Fields** (required type: string)

- **name**, **identifier**, **organization**, **status**, **repositoryURL**, **vcs**, **feedbackMechanism**
- If present and not null:
  - Must be string type
  - Non-string → **ERROR:** "Field '{name}' must be string, got {type}"

#### **Object Fields** (required type: object)

- **permissions** (required sub-object with structure checks below)
- **reuseFrequency** (optional object)
- **contact** (required object)
- If present and not null:
  - Must be object type
  - Non-object → **ERROR:** "Field '{name}' must be object, got {type}"

#### **Optional Date Object**

- `date` may be absent. If present, it must be an object, including when supplied
  directly to validation without normalization.
- Any non-object value (including null or an array) produces an error:
  `Field 'date' must be object, got {type}`.
- Stage 3a omits nulls, empty arrays, and placeholder-only arrays before validation.
  Other malformed date containers remain available for this check to report.
- This check does not change the value or block record retention, and does not
  validate the date object's timestamp formats.

#### **Array Fields** (required type: array)

- **contractNumber** (array of strings)
- If present and not null:
  - Must be array type
  - Non-array → **ERROR:** "Field '{name}' must be array, got {type}"

---

### **Permissions Object Structure** (STRICT)

Required structure at **permissions.{licenses, usageType}**

#### **permissions.licenses (array, required)**

- Must be present in permissions object
- Must be array type (not null)
  - If not array → **ERROR:** "permissions.licenses must be array, got {type}"

**Per license item:**

- Cannot be null → **ERROR:** "permissions.licenses[{i}] cannot be null"
- Must be object (dict)
  - If not object → **ERROR:** (implicit, skipped in validation loop)
- Must have **name** field
  - Missing → **ERROR:** "permissions.licenses[{i}].name is required"
  - If name not in LICENSE_ENUM → **WARNING:** "'{value}' is not a standard license enum value (keeping as-is)"
- Must have **URL** field
  - Missing → **ERROR:** "permissions.licenses[{i}].URL is required"

**License enum:**

```
CC0-1.0, Apache-2.0, MIT, MPL-2.0, GPL-2.0-only, GPL-3.0-only,
GPL-3.0-or-later, LGPL-2.1-only, LGPL-3.0-only, BSD-2-Clause,
BSD-3-Clause, EPL-2.0, Other, None
```

#### **permissions.usageType (array, required)**

- Must be present in permissions object
- Must be array type (not null)
  - If not array → **ERROR:** "permissions.usageType must be array, got {type}"

**Per usage item:**

- Cannot be null → **ERROR:** "permissions.usageType[{i}] cannot be null"
- If present and not in USAGE_ENUM → **WARNING:** "'{value}' is not a standard usageType enum value (keeping as-is)"

**Usage type enum:**

```
openSource, governmentWideReuse, exemptByNationalSecurity,
exemptByNationalIntelligence, exemptByFOIA, exemptByEAR, exemptByITAR,
exemptByTSA, exemptByClassifiedInformation, exemptByPrivacyRisk,
exemptByDisposableCode, exemptByExperimentalCode,
exemptByCommercialSoftware
```

---

### **Enum Fields (Soft Warnings)**

_These don't block validation; warnings are issued for unrecognized values_

#### **status**

- If present and not null:
  - Must be string type
    - Non-string → **ERROR:** "status must be string, got {type}"
  - If not in STATUS_ENUM → **WARNING:** "status: '{value}' is not a standard status enum value (will attempt to standardize)"

**Status enum:**

```
Ideation, Development, Alpha, Beta, Release Candidate,
Production, Archival
```

#### **vcs**

- If present and not null:
  - Must be string type
    - Non-string → **ERROR:** "vcs must be string, got {type}"
  - If not in VCS_ENUM → **WARNING:** "vcs: '{value}' is not a standard vcs enum value (keeping as-is)"

**VCS enum:**

```
git, hg, svn, rcs, bzr, none
```

#### **maintenance**

- If present and not null:
  - Must be string type
    - Non-string → **ERROR:** "maintenance must be string, got {type}"
  - If not in MAINTENANCE_ENUM → **WARNING:** "maintenance: '{value}' is not a standard maintenance enum value (keeping as-is)"

**Maintenance enum:**

```
internal, contract, community, none
```

#### **repositoryVisibility**

- If present and not null:
  - Must be string type
    - Non-string → **ERROR:** "repositoryVisibility must be string, got {type}"
  - If not in VISIBILITY_ENUM → **WARNING:** "repositoryVisibility: '{value}' is not a standard visibility enum value (keeping as-is)"

**Visibility enum:**

```
public, private
```

---

## **STAGE 2: FILL & STANDARDIZE** (`fill_record`)

Fills missing required fields and standardizes known enum values.

### **Permissions Object Filling**

If `permissions` is missing or null:

- Create: `{"licenses": [], "usageType": []}`
- Derivation: "added empty licenses/usageType"

If `permissions` is object but keys are missing:

- Add missing **licenses** array → `[]`
- Add missing **usageType** array → `[]`
- Derivation: "added empty list" (per key)

**Clean null items:**

- Remove null items from licenses and usageType arrays

**Standardize License Names:**

- For each license item with a `name` field:
  - Look up original name in LICENSE_MAP (case-insensitive)
  - If found → replace with mapped standard name
    - Derivation: `"mapped from '{original}' to '{standard}'"`
  - If mapped to `null` (e.g., "noassertion") → drop that mapping
    - Derivation: `"dropped '{original}' (no usable mapping)"`
  - If not found → keep original
    - Derivation: `"not mappable, kept as '{original}'"`

**License mapping includes:**

- MIT family: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause
- GPL family: GPL-2.0-only, GPL-3.0-only, GPL-3.0-or-later
- LGPL family: LGPL-2.1-only, LGPL-3.0-only
- Other: MPL-2.0, EPL-2.0, CC0-1.0
- Special: "noassertion" → drops (no mapping)
- See [validate.py LICENSE_MAP](../scripts/utils/validate.py) for full mappings

---

### **Repository URL Filling**

If `repositoryURL` is missing or null:

- **If record is closed code** (has exempt usageType, no openSource):
  - Set to `"private"`
  - Derivation: `'closed code, no URL provided -> "private"'`
- **Otherwise:**
  - Set to `null`
  - Derivation: `"not provided, not closed code"`

---

### **Repository Visibility Inferring**

If `repositoryVisibility` is missing or null:

- **If repositoryURL is "private" (string, case-insensitive):**
  - Set to `"private"`
  - Derivation: `'inferred from repositoryURL = "private"'`
- **Otherwise:**
  - Set to `null`
  - Derivation: `"not provided; repository URL does not establish visibility"`

An HTTP(S) URL, including a GitHub URL, does not establish public visibility.
Existing non-null `repositoryVisibility` values are preserved by filling.
Unknown visibility remains null and does not satisfy the schema's enum; it is
not replaced with a guessed value. VCS and feedback inference are unaffected.

---

### **Agency Identifier Preservation**

Preserve the agency's `identifier` (including legacy `id` mapping during
normalization). If missing or null, include `identifier: null`. Blank strings
become null during normalization. No repository URL or name hash is used.
The derivation log records `"not supplied by agency"` for absent values.

`govcode_id` is assigned only by the collectors and carried through unchanged.
Consolidation rejects missing, malformed, or duplicate local IDs before writing
output. The local release validation contract requires `identifier` to be
present and permits string or null, and requires a string `govcode_id`.
The fetched agency schema currently supplies agency/version configuration; this
is not a full validation against the remote project schema.

---

### **Organization Inferring**

If `organization` is missing or null:

- Set to **agency folder name** (e.g., "DHS", "DoD")
- Derivation: `"inferred from agency folder name"`

---

### **Status Standardizing**

If `status` is present and is a string:

- **Attempt to standardize** using STATUS_MAP and prefix matching:
  - Exact match (case-insensitive): Use mapped canonical value
  - Prefix match: Check if starts with known prefix (alpha, beta, release candidate)
  - If matches → set to canonical value
    - Derivation: `"standardized from '{original}' to '{standard}'"`
  - If no match → keep original
    - Derivation: `"not mappable, kept as '{original}'"`

If `status` is missing or null:

- Do not guess
- Derivation: `"not provided, not filled (don't guess enum)"`

**Status mapping:**

```
ideation → Ideation
development → Development
alpha → Alpha
beta → Beta
release candidate / release-candidate / rc → Release Candidate
production → Production
archival → Archival
(prefix match for alpha, beta, release candidate)
```

---

### **Maintenance Field**

If `maintenance` is missing or null:

- Set to `null` (do not guess)
- Derivation: `"not provided, not filled (don't guess enum)"`

If provided → keep as-is (even if not in enum)

---

### **VCS Inferring**

If `vcs` is missing or null:

- **If repositoryURL is a github.com repository:**
  - Set to `"git"`
  - Derivation: `"inferred from github.com repository"`
- **Otherwise:**
  - Set to `null`
  - Derivation: `"not provided, not a github repo"`

If provided → keep as-is (even if not in enum)

---

### **Feedback Mechanism Inferring**

If `feedbackMechanism` is missing or null:

- **If repositoryURL is a github.com repository:**
  - Extract owner and repo from URL
  - Set to `"https://github.com/{owner}/{repo}/issues"`
  - Derivation: `"inferred from github issues URL"`
  - Example: `https://github.com/user/project/issues`
- **Otherwise:**
  - Set to `null`
  - Derivation: `"not provided, not a github repo"`

If provided → keep as-is

---

### **Reuse Frequency**

If `reuseFrequency` is missing or null:

- Create empty object: `{}`
- Derivation: `"added empty object"`

If provided → keep as-is (no standardization applied)

---

### **Contract Number**

If `contractNumber` is missing or null:

- Create empty array: `[]`
- Derivation: `"added empty array"`

If provided → keep as-is (no standardization applied)

---

### **Contact Object**

If `contact` is missing or null:

- Create empty object: `{}`
- Derivation: `"added empty object"`

If provided → keep as-is (no field standardization applied)

---

### **Safety Net & Field Ordering**

After all fills and derivations:

1. **Ensure all required fields exist** (add as null if missing, should not happen)
2. **Order output:** Required fields first (in fixed order), then all other fields

---

## **Helper Functions**

### **usable_url(value)**

- Returns `True` if value is a valid http/https URL with netloc
- Excludes: empty string, "private" (case-insensitive), non-string types
- Uses `urlsplit(value).scheme in ("http", "https")` and checks netloc

### **is_github_repo(url)**

- Returns `True` if URL is a valid github.com or www.github.com repository
- Must pass `usable_url(url)` check first

### **github_repo(url)**

- Extracts `(owner, repo)` tuple from github.com URL
- Strips `.git` suffix from repo name
- Returns `None` if URL is not a valid github.com repository or lacks enough path segments

### **is_closed(record)**

- Checks if record represents closed/exempt code
- Returns `True` if:
  - permissions.usageType contains a string starting with "exempt"
  - **AND** "openSource" is NOT in permissions.usageType

### **slugify(string)**

- Converts string to kebab-case (lowercase, hyphens)
- Removes non-alphanumeric characters (except hyphens)
- Caps at 40 characters
- Returns "unnamed" if result is empty

---

## **Summary**

| **Stage**                 | **Purpose**                 | **Key Operations**                                                     |
| ------------------------- | --------------------------- | ---------------------------------------------------------------------- |
| **1: Validate**           | Check structure & types     | Required fields, type checks, soft enum warnings                       |
| **2: Fill & Standardize** | Derive defaults & normalize | Infer org/vcs/feedback, standardize status/licenses, preserve unknowns |

Both stages return an **audit trail** via error/warning lists or derivation dict, enabling full traceability of what changed and why.

## HHS supplied-field CMS checks

After normalization and before required-field filling, `cms_diagnostics` marks
an HHS record as CMS-style when any field listed in the CMS-style normalization
section is present in the original object, even if its value is null or empty.
Agency comparison ignores case and surrounding whitespace. Other agencies and
HHS records without those fields receive no CMS-specific checks.

The marker is returned in diagnostics and logged at INFO; it is never inserted
into project JSON. Each violation is logged at WARNING with filename and field
path. Checks are non-blocking and do not drop projects.

Validation uses the pinned CMS 2.2.0 schema, Draft 2020-12, and format checking
(`jsonschema[format]`, installed via `scripts/requirements.txt`). It retains
supplied-field types, enums, unique-item rules, bounds, description lengths, and
URI/date-time/email formats. Required-key and additional-property restrictions
are removed recursively: missing fields, missing nested fields, and extensions
are not errors. The organization enum is removed to avoid identity inference.
`repositoryURL: "private"` is accepted as explicitly allowed by the source
schema's description despite its URI format declaration.

Normalized values are checked; when existing cleanup removes a supplied
top-level field, its original value is checked so its issue remains visible.
Checks happen before filling to avoid validating inferred/default fields.
The CMS repositoryHost enum is enforced only in this HHS diagnostic path.
No full CMS conformance or ownership classification is performed. Existing
base validation and filling remain independent and unchanged.

### Structural metadata validation

Contract number arrays must contain strings; description and longDescription
must be strings when non-null; date must be an object or null. CMS supplied-field
checks explicitly allow date null as the normalized representation of a
placeholder date. This is a documented local exception to CMS 2.2.0, whose date
property only permits objects. These checks remain non-blocking.
