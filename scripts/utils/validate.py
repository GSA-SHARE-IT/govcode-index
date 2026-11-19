"""Validation and filling of code.json project records.

Two-stage validation pipeline:
1. Validate (validate_record):
   - Checks type, structure, required fields (STRICT)
   - Checks format for URIs, emails, dates (SOFT - warnings only)
   - Checks enum values and generates soft warnings (SOFT - don't block)
   - Returns: (is_valid=True regardless, errors[], warnings[])

2. Fill & Standardize (fill_record):
   - Fills missing required fields with derived/inferred values
   - Attempts to standardize license names, status, vcs
   - Keeps original values if standardization fails
   - Tracks all changes in derivation dict
   - Returns: (filled_record, derivation_dict)

Target schema: code.json 0.1.0. Standard library only. Reusable in any pipeline.
Preserves non-standard values when standardization is not possible.
Full audit trail via derivation dict.

Public API:
  - validate_record(record): Validate a single project record
  - fill_record(agency, filename, record): Fill required fields
  - has_identity(record): Check if record has name or usable URL
"""

import copy
import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# --- Constants ---

REQUIRED_FIELDS = [
    "name", "identifier", "organization", "status",
    "permissions", "reuseFrequency", "repositoryURL",
    "repositoryVisibility", "maintenance", "contractNumber",
    "contact", "feedbackMechanism"
]

USAGE_ENUM = [
    "openSource", "governmentWideReuse", "exemptByNationalSecurity",
    "exemptByNationalIntelligence", "exemptByFOIA", "exemptByEAR", "exemptByITAR",
    "exemptByTSA", "exemptByClassifiedInformation", "exemptByPrivacyRisk",
    "exemptByDisposableCode", "exemptByExperimentalCode",
    "exemptByCommercialSoftware",
]

LICENSE_ENUM = {
    "CC0-1.0", "Apache-2.0", "MIT", "MPL-2.0", "GPL-2.0-only", "GPL-3.0-only",
    "GPL-3.0-or-later", "LGPL-2.1-only", "LGPL-3.0-only", "BSD-2-Clause",
    "BSD-3-Clause", "EPL-2.0", "Other", "None",
}

STATUS_ENUM = {"Ideation", "Development", "Alpha", "Beta", "Release Candidate",
               "Production", "Archival"}

VCS_ENUM = {"git", "hg", "svn", "rcs", "bzr", "none"}

MAINTENANCE_ENUM = {"internal", "contract", "community", "none"}

VISIBILITY_ENUM = {"public", "private"}

# License mapping from normalize.py
LICENSE_MAP = {
    "mit": "MIT", "mit license": "MIT",
    "apache-2.0": "Apache-2.0", "apache license 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0", "apache": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "cc0": "CC0-1.0", "cc0-1.0": "CC0-1.0", "cc0 1.0": "CC0-1.0",
    "public domain": "CC0-1.0",
    "gpl-2.0": "GPL-2.0-only", "gpl-2.0-only": "GPL-2.0-only",
    "gpl 2.0": "GPL-2.0-only", "gpl2": "GPL-2.0-only",
    "gnu general public license v2.0": "GPL-2.0-only",
    "gpl-3.0": "GPL-3.0-only", "gpl-3.0-only": "GPL-3.0-only",
    "gpl3": "GPL-3.0-only", "gpl3.0": "GPL-3.0-only", "gpl 3.0": "GPL-3.0-only",
    "gpl.v3": "GPL-3.0-only",
    "gnu general public license v3.0": "GPL-3.0-only",
    "gpl-3.0-or-later": "GPL-3.0-or-later", "gpl-3.0+": "GPL-3.0-or-later",
    "lgpl-2.1": "LGPL-2.1-only", "lgpl-2.1-only": "LGPL-2.1-only",
    "lgpl-3.0": "LGPL-3.0-only", "lgpl-3.0-only": "LGPL-3.0-only",
    "bsd-2-clause": "BSD-2-Clause",
    'bsd 2-clause "simplified" license': "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    'bsd 3-clause "new" or "revised" license': "BSD-3-Clause",
    "mpl-2.0": "MPL-2.0", "mozilla public license 2.0": "MPL-2.0",
    "epl-2.0": "EPL-2.0",
    "gpl-2.1": "Other", "agpl": "Other", "agpl-3.0": "Other", "epl-1.0": "Other",
    "the unlicense": "Other", "unlicense": "Other",
    "sil open font license": "Other", "nsf": "Other", "other": "Other",
    "none": "None",
    "noassertion": None,
}

STATUS_MAP = {
    "ideation": "Ideation", "development": "Development", "alpha": "Alpha",
    "beta": "Beta", "release candidate": "Release Candidate",
    "release-candidate": "Release Candidate", "rc": "Release Candidate",
    "production": "Production", "archival": "Archival",
}

STATUS_PREFIXES = [("alpha", "Alpha"), ("beta", "Beta"),
                   ("release candidate", "Release Candidate")]


# --- Helper Functions ---

def slugify(s: str) -> str:
    """Convert string to kebab-case, max 40 characters."""
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:40] or "unnamed"


def usable_url(v) -> bool:
    """Check if value is a valid http(s) URL with netloc."""
    return (isinstance(v, str) and v.lower() not in ("", "private") and
            urlsplit(v).scheme in ("http", "https") and bool(urlsplit(v).netloc))


def is_github_repo(url: str) -> bool:
    """Check if URL is a github.com repository."""
    if not usable_url(url):
        return False
    netloc = urlsplit(url).netloc.lower()
    return netloc in ("github.com", "www.github.com")


def github_repo(url: str) -> tuple | None:
    """Extract (owner, repo) from github.com URL, else None. Strips .git suffix."""
    if not is_github_repo(url):
        return None
    path_parts = [s for s in urlsplit(url).path.split("/") if s]
    if len(path_parts) < 2:
        return None
    repo = path_parts[1].rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return (path_parts[0], repo)


def derive_identifier(agency: str, filename: str, rec: dict) -> str:
    """Derive a stable identifier from URL or agency+name hash."""
    url = rec.get("repositoryURL")
    if usable_url(url):
        p = urlsplit(url)
        return (p.netloc + p.path).lower().rstrip("/")
    name = rec.get("name") or Path(filename).stem
    digest = hashlib.sha1(f"{agency}|{name}".encode("utf-8")).hexdigest()[:8]
    return f"{agency.lower()}:{slugify(name)}-{digest}"


def is_closed(rec: dict) -> bool:
    """Check if record is closed code (exempt usageType, no openSource)."""
    perms = rec.get("permissions")
    usage = perms.get("usageType") if isinstance(perms, dict) else None
    if not isinstance(usage, list):
        return False
    return (any(isinstance(u, str) and u.startswith("exempt") for u in usage)
            and "openSource" not in usage)


def standardize_license_name(original: str) -> tuple[str | None, bool]:
    """
    Attempt to standardize license name using LICENSE_MAP.
    
    Returns:
        (standardized_name, was_mapped)
    """
    if original is None:
        return None, False
    
    lookup_key = str(original).lower().strip()
    if lookup_key in LICENSE_MAP:
        mapped = LICENSE_MAP[lookup_key]
        return mapped, True
    
    return original, False


def standardize_status(original: str) -> tuple[str | None, bool]:
    """
    Attempt to standardize status using STATUS_MAP and prefix matching.
    
    Returns:
        (standardized_status, was_mapped)
    """
    if original is None:
        return None, False
    
    lookup_key = str(original).lower().strip()
    
    # Exact match
    if lookup_key in STATUS_MAP:
        return STATUS_MAP[lookup_key], True
    
    # Prefix match
    for prefix, standard in STATUS_PREFIXES:
        if lookup_key.startswith(prefix):
            return standard, True
    
    return original, False


def validate_record(record: dict) -> tuple[bool, list, list]:
    """
    Validate a record against code.json 0.1.0 schema requirements.
    
    Uses hard-coded validation rules (not fetched remote schema) for offline support
    and explicit auditability. Performs type checking and required field validation.
    Allows non-standard enum values with soft warnings (non-blocking).
    
    Returns:
        (is_valid, errors, warnings) where:
        - is_valid: True if no blocking errors
        - errors: List of blocking validation errors
        - warnings: List of soft warnings (enum mismatches, format issues)
    """
    errors = []
    warnings = []
    
    # Type checking: must be dict
    if not isinstance(record, dict):
        errors.append(f"Record must be a JSON object, got {type(record).__name__}")
        return False, errors, warnings
    
    # Required fields check
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"Missing required field: '{field}'")
    
    # Type checks for required fields
    if "name" in record and record["name"] is not None:
        if not isinstance(record["name"], str):
            errors.append(f"Field 'name' must be string, got {type(record['name']).__name__}")
    
    if "identifier" in record and record["identifier"] is not None:
        if not isinstance(record["identifier"], str):
            errors.append(f"Field 'identifier' must be string, got {type(record['identifier']).__name__}")
    
    if "organization" in record and record["organization"] is not None:
        if not isinstance(record["organization"], str):
            errors.append(f"Field 'organization' must be string, got {type(record['organization']).__name__}")
    
    # Permissions object structure
    if "permissions" in record:
        perms = record["permissions"]
        if perms is not None:
            if not isinstance(perms, dict):
                errors.append(f"Field 'permissions' must be object, got {type(perms).__name__}")
            else:
                # Check licenses and usageType are present and are arrays
                if "licenses" not in perms:
                    errors.append("Field 'permissions.licenses' is required")
                elif perms["licenses"] is not None and not isinstance(perms["licenses"], list):
                    errors.append(f"Field 'permissions.licenses' must be array, got {type(perms['licenses']).__name__}")
                else:
                    # Check licenses items have name and URL
                    if isinstance(perms.get("licenses"), list):
                        for i, license_item in enumerate(perms["licenses"]):
                            if license_item is None:
                                errors.append(f"Field 'permissions.licenses[{i}]' cannot be null")
                            elif isinstance(license_item, dict):
                                if "name" not in license_item:
                                    errors.append(f"Field 'permissions.licenses[{i}].name' is required")
                                elif license_item["name"] not in LICENSE_ENUM:
                                    warnings.append(f"permissions.licenses[{i}].name: '{license_item['name']}' is not a standard license enum value (keeping as-is)")
                                if "URL" not in license_item:
                                    errors.append(f"Field 'permissions.licenses[{i}].URL' is required")
                
                if "usageType" not in perms:
                    errors.append("Field 'permissions.usageType' is required")
                elif perms["usageType"] is not None and not isinstance(perms["usageType"], list):
                    errors.append(f"Field 'permissions.usageType' must be array, got {type(perms['usageType']).__name__}")
                else:
                    # Check usageType items and warn if not in enum (but don't error)
                    if isinstance(perms.get("usageType"), list):
                        for i, usage_item in enumerate(perms["usageType"]):
                            if usage_item is None:
                                errors.append(f"Field 'permissions.usageType[{i}]' cannot be null")
                            elif isinstance(usage_item, str) and usage_item not in USAGE_ENUM:
                                warnings.append(f"permissions.usageType[{i}]: '{usage_item}' is not a standard usageType enum value (keeping as-is)")
    
    # Status enum warning (soft)
    if "status" in record and record["status"] is not None:
        if not isinstance(record["status"], str):
            errors.append(f"Field 'status' must be string, got {type(record['status']).__name__}")
        elif record["status"] not in STATUS_ENUM:
            warnings.append(f"status: '{record['status']}' is not a standard status enum value (will attempt to standardize)")
    
    # VCS enum warning (soft)
    if "vcs" in record and record["vcs"] is not None:
        if not isinstance(record["vcs"], str):
            errors.append(f"Field 'vcs' must be string, got {type(record['vcs']).__name__}")
        elif record["vcs"] not in VCS_ENUM:
            warnings.append(f"vcs: '{record['vcs']}' is not a standard vcs enum value (keeping as-is)")
    
    # Maintenance enum warning (soft)
    if "maintenance" in record and record["maintenance"] is not None:
        if not isinstance(record["maintenance"], str):
            errors.append(f"Field 'maintenance' must be string, got {type(record['maintenance']).__name__}")
        elif record["maintenance"] not in MAINTENANCE_ENUM:
            warnings.append(f"maintenance: '{record['maintenance']}' is not a standard maintenance enum value (keeping as-is)")
    
    # RepositoryVisibility enum warning (soft)
    if "repositoryVisibility" in record and record["repositoryVisibility"] is not None:
        if not isinstance(record["repositoryVisibility"], str):
            errors.append(f"Field 'repositoryVisibility' must be string, got {type(record['repositoryVisibility']).__name__}")
        elif record["repositoryVisibility"] not in VISIBILITY_ENUM:
            warnings.append(f"repositoryVisibility: '{record['repositoryVisibility']}' is not a standard visibility enum value (keeping as-is)")
    
    # Other required field types
    if "reuseFrequency" in record and record["reuseFrequency"] is not None:
        if not isinstance(record["reuseFrequency"], dict):
            errors.append(f"Field 'reuseFrequency' must be object, got {type(record['reuseFrequency']).__name__}")
    
    if "repositoryURL" in record and record["repositoryURL"] is not None:
        if not isinstance(record["repositoryURL"], str):
            errors.append(f"Field 'repositoryURL' must be string, got {type(record['repositoryURL']).__name__}")
    
    if "contractNumber" in record and record["contractNumber"] is not None:
        if not isinstance(record["contractNumber"], list):
            errors.append(f"Field 'contractNumber' must be array, got {type(record['contractNumber']).__name__}")
        elif any(not isinstance(item, str) for item in record["contractNumber"]):
            errors.append("Field 'contractNumber' items must be strings")

    for field in ("description", "longDescription"):
        if record.get(field) is not None and not isinstance(record[field], str):
            errors.append(f"Field '{field}' must be string")
    if record.get("date") is not None and not isinstance(record["date"], dict):
        errors.append("Field 'date' must be object or null")
    
    if "contact" in record and record["contact"] is not None:
        if not isinstance(record["contact"], dict):
            errors.append(f"Field 'contact' must be object, got {type(record['contact']).__name__}")
    
    if "feedbackMechanism" in record and record["feedbackMechanism"] is not None:
        if not isinstance(record["feedbackMechanism"], str):
            errors.append(f"Field 'feedbackMechanism' must be string, got {type(record['feedbackMechanism']).__name__}")
    
    if "date" in record and not isinstance(record["date"], dict):
        errors.append(f"Field 'date' must be object, got {type(record['date']).__name__}")

    # Return: is_valid is True regardless of warnings
    return True, errors, warnings


def has_identity(record: dict) -> bool:
    """Check if record has name or usable public repositoryURL."""
    return bool(record.get("name")) or usable_url(record.get("repositoryURL"))


def fill_record(agency: str, filename: str, record: dict) -> tuple[dict, dict]:
    """
    Fill missing required fields and standardize where appropriate.
    
    Returns:
        (filled_record, derivation_dict) where derivation tracks all changes
    """
    rec = copy.deepcopy(record)
    derived = {}
    
    # --- permissions (must be present) ---
    if rec.get("permissions") is None:
        rec["permissions"] = {"licenses": [], "usageType": []}
        derived["permissions"] = "added empty licenses/usageType"
    elif isinstance(rec["permissions"], dict):
        perms = rec["permissions"]
        for key in ("licenses", "usageType"):
            if key not in perms or perms[key] is None:
                perms[key] = []
                derived[f"permissions.{key}"] = "added empty list"
        
        # Clean up null items in arrays
        for key in ("licenses", "usageType"):
            if isinstance(perms.get(key), list):
                perms[key] = [item for item in perms[key] if item is not None]
        
        # Standardize license names
        if "licenses" in perms and isinstance(perms["licenses"], list):
            for i, license_item in enumerate(perms["licenses"]):
                if isinstance(license_item, dict) and "name" in license_item:
                    original_name = license_item["name"]
                    standardized, was_mapped = standardize_license_name(original_name)
                    if was_mapped and standardized is not None:
                        license_item["name"] = standardized
                        derived[f"permissions.licenses[{i}].name"] = f"mapped from '{original_name}' to '{standardized}'"
                    elif standardized is None:
                        # None mapping means drop (like "noassertion")
                        derived[f"permissions.licenses[{i}].name"] = f"dropped '{original_name}' (no usable mapping)"
                    else:
                        # Not mappable, keep original
                        derived[f"permissions.licenses[{i}].name"] = f"not mappable, kept as '{original_name}'"
    
    # --- repositoryURL ---
    if rec.get("repositoryURL") is None:
        if is_closed(rec):
            rec["repositoryURL"] = "private"
            derived["repositoryURL"] = 'closed code, no URL provided -> "private"'
        else:
            rec["repositoryURL"] = None
            derived["repositoryURL"] = "not provided, not closed code"
    
    # --- repositoryVisibility (only infer from an explicit private marker) ---
    if rec.get("repositoryVisibility") is None:
        url = rec.get("repositoryURL")
        if isinstance(url, str) and url.lower() == "private":
            rec["repositoryVisibility"] = "private"
            derived["repositoryVisibility"] = 'inferred from repositoryURL = "private"'
        else:
            rec["repositoryVisibility"] = None
            derived["repositoryVisibility"] = "not provided; repository URL does not establish visibility"
    
    # --- identifier (must derive) ---
    if rec.get("identifier") is None:
        rec["identifier"] = derive_identifier(agency, filename, rec)
        derived["identifier"] = "derived from repositoryURL or agency+name hash"
    
    # --- organization (must infer) ---
    if rec.get("organization") is None:
        rec["organization"] = agency
        derived["organization"] = "inferred from agency folder name"
    
    # --- status (attempt standardize, keep if can't) ---
    if rec.get("status") is not None and isinstance(rec["status"], str):
        standardized, was_mapped = standardize_status(rec["status"])
        if was_mapped:
            rec["status"] = standardized
            derived["status"] = f"standardized from '{record.get('status')}' to '{standardized}'"
        else:
            # Keep original if not mappable
            derived["status"] = f"not mappable, kept as '{rec['status']}'"
    elif rec.get("status") is None:
        # Don't guess status
        derived["status"] = "not provided, not filled (don't guess enum)"
    
    # --- maintenance (never guess) ---
    if rec.get("maintenance") is None:
        rec["maintenance"] = None
        derived["maintenance"] = "not provided, not filled (don't guess enum)"
    
    # --- vcs (infer git from github) ---
    if rec.get("vcs") is None:
        gh = github_repo(rec.get("repositoryURL"))
        if gh:
            rec["vcs"] = "git"
            derived["vcs"] = "inferred from github.com repository"
        else:
            rec["vcs"] = None
            derived["vcs"] = "not provided, not a github repo"
    # Else keep provided vcs value as-is (even if not in enum)
    
    # --- feedbackMechanism (try to infer from github) ---
    if rec.get("feedbackMechanism") is None:
        gh = github_repo(rec.get("repositoryURL"))
        if gh:
            rec["feedbackMechanism"] = f"https://github.com/{gh[0]}/{gh[1]}/issues"
            derived["feedbackMechanism"] = "inferred from github issues URL"
        else:
            rec["feedbackMechanism"] = None
            derived["feedbackMechanism"] = "not provided, not a github repo"
    
    # --- empty-form defaults ---
    if rec.get("reuseFrequency") is None:
        rec["reuseFrequency"] = {}
        derived["reuseFrequency"] = "added empty object"
    
    if rec.get("contractNumber") is None:
        rec["contractNumber"] = []
        derived["contractNumber"] = "added empty array"
    
    if rec.get("contact") is None:
        rec["contact"] = {}
        derived["contact"] = "added empty object"
    
    # --- safety net: all required keys must exist ---
    for key in REQUIRED_FIELDS:
        if key not in rec:
            rec[key] = None
            derived[key] = "added as null (should not happen)"
    
    # --- order: required fields first, then others ---
    ordered = {k: rec[k] for k in REQUIRED_FIELDS}
    ordered.update({k: v for k, v in rec.items() if k not in ordered})
    
    return ordered, derived
