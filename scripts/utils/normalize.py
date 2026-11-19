"""Normalization of code.json project records.
Two-stage normalization pipeline:
Structural Normalization (apply_structural_normalization):
  - Fixes the SHAPE of records: renames legacy keys, hoists misplaced fields,
    strips forbidden nested keys, coerces types, trims strings, handles empty values.
  - Functions prefixed with struct_* focus on record structure and type coercion.
Value Normalization (apply_value_normalization):
  - Normalizes VALUES: licenses, usageType, status, dates, URLs, tags, etc.
  - Canonicalizes URLs, validates emails, enforces enums, parses date formats.
  - Functions prefixed with value_* focus on value validation and mapping.
Target schema: code.json 0.1.0. Standard library only. Reusable in any pipeline.
Idempotent: normalizing twice produces identical results.
Public API:
  - normalize_project(project): Normalize a single project dict.
  - normalize_record(src, ctx=None): Internal; normalize with optional context.
"""

import copy
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

# --- schema knowledge (code.json 0.1.0) --------------------------------------

SCHEMA_KEYS = {
    "name", "identifier", "version", "description", "organization", "status",
    "permissions", "reuseFrequency", "repositoryURL", "repositoryVisibility",
    "homepageURL", "downloadURL", "disclaimerURL", "disclaimerText", "vcs",
    "laborHours", "languages", "maintenance", "contractNumber", "SBOM",
    "relatedCode", "reusedCode", "partners", "date", "tags", "contact",
    "feedbackMechanism", "AIUseCaseID",
}

# Required string fields: empty string -> null (only if the key is present).
REQUIRED_STRINGS = [
    "name", "identifier", "organization", "status", "repositoryURL",
    "repositoryVisibility", "maintenance", "feedbackMechanism",
]
# Optional string fields: empty / null -> key omitted. ("version" is separate.)
OPTIONAL_STRINGS = [
    "description", "longDescription", "homepageURL", "downloadURL", "disclaimerURL",
    "disclaimerText", "vcs", "SBOM", "AIUseCaseID",
]

PERMISSIONS_KEYS = {"licenses", "usageType", "exemptionText"}
LICENSE_KEYS = {"name", "URL"}
CONTACT_KEYS = {"email", "name"}
DATE_KEYS = {"created", "lastModified", "metadataLastUpdated"}
RELATED_KEYS = {"name", "URL", "isGovernmentRepo"}
REUSED_KEYS = {"name", "URL"}
PARTNER_KEYS = {"name", "email"}

# Confident legacy renames only.
TOP_LEVEL_RENAMES = [("repository", "repositoryURL"),
                     ("homepage", "homepageURL"),
                     ("id", "identifier")]

# --- enums (code.json 0.1.0) for value normalization -------------------------

LICENSE_ENUM = {
    "CC0-1.0", "Apache-2.0", "MIT", "MPL-2.0", "GPL-2.0-only", "GPL-3.0-only",
    "GPL-3.0-or-later", "LGPL-2.1-only", "LGPL-3.0-only", "BSD-2-Clause",
    "BSD-3-Clause", "EPL-2.0", "Other", "None",
}
STATUS_ENUM = {"Ideation", "Development", "Alpha", "Beta", "Release Candidate",
               "Production", "Archival"}
USAGE_ENUM = [
    "openSource", "governmentWideReuse", "exemptByNationalSecurity",
    "exemptByNationalIntelligence", "exemptByFOIA", "exemptByEAR", "exemptByITAR",
    "exemptByTSA", "exemptByClassifiedInformation", "exemptByPrivacyRisk",
    "exemptByDisposableCode", "exemptByExperimentalCode",
    "exemptByCommercialSoftware",
]
# Not in schema 0.1.0, but kept verbatim by decision
USAGE_LEGACY = ["exemptByAgencySystem", "exemptByAgencyMission", "exemptByLaw"]
USAGE_LOOKUP = {v.lower(): v for v in USAGE_ENUM + USAGE_LEGACY}

VCS_ENUM = {"git", "hg", "svn", "rcs", "bzr", "none"}
VISIBILITY_ENUM = {"public", "private"}
MAINTENANCE_ENUM = {"internal", "contract", "community", "none"}

# License mapping: normalized key -> enum value (None = drop the item)
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
    # known licenses the schema enum cannot express
    "gpl-2.1": "Other", "agpl": "Other", "agpl-3.0": "Other", "epl-1.0": "Other",
    "the unlicense": "Other", "unlicense": "Other",
    "sil open font license": "Other", "nsf": "Other", "other": "Other",
    "none": "None",
    # no usable license information
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

# Regex patterns for date and email validation
DATE_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?)?$")
SLASH_YMD = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
TEXT_FORMATS = ["%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")



# --- helpers ----------------------------------------------------------------

class Ctx:
    """Per-file change log. Logs action names, never values."""

    def __init__(self):
        self.changes = Counter()

    def log(self, action):
        self.changes[action] += 1


def is_empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def to_number(v):
    """Return int/float for numbers and numeric strings, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None
    return None


def strip_extra(ctx, d, allowed, path):
    for k in list(d):
        if k not in allowed:
            del d[k]
            ctx.log(f"dropped_nested_key:{path}.{k}")


def trim_str(ctx, d, key, path):
    v = d.get(key)
    if isinstance(v, str):
        s = v.strip()
        if s != v:
            ctx.log(f"trimmed:{path}")
        d[key] = s


def clean_str_list(ctx, v, where):
    """Wrap a string, trim items, drop empty/non-string items.
    Returns (list, original_was_string) or (None, False) if not coercible."""
    was_str = False
    if isinstance(v, str):
        v = [v]
        was_str = True
        ctx.log(f"wrapped_string_in_list:{where}")
    if not isinstance(v, list):
        return None, False
    out = []
    for item in v:
        if isinstance(item, str):
            s = item.strip()
            if s and s != "None":
                out.append(s)
                if s != item:
                    ctx.log(f"trimmed:{where}[]")
            elif s == "None":
                ctx.log(f"dropped_none_literal:{where}")
            else:
                ctx.log(f"dropped_empty_item:{where}")
        else:
            ctx.log(f"dropped_non_string_item:{where}")
    return out, was_str


# --- normalization functions ------------------------------------------------

def rename_top_level(ctx, rec):
    for old, new in TOP_LEVEL_RENAMES:
        if old not in rec:
            continue
        val = rec.pop(old)
        if new not in rec or is_empty(rec[new]):
            rec[new] = val
            ctx.log(f"renamed:{old}->{new}")
        else:
            ctx.log(f"dropped_legacy_key_conflict:{old}")


def rename_updated(ctx, rec):
    """Legacy `updated` -> date.lastModified (schema key wins on conflict)."""
    if "updated" not in rec:
        return
    if "date" not in rec or rec["date"] is None:
        rec["date"] = {}
    date = rec["date"]
    if not isinstance(date, dict):
        ctx.log("skipped_rename:updated(date not an object)")
        return
    val = rec.pop("updated")
    if is_empty(date.get("lastModified")):
        date["lastModified"] = val
        ctx.log("renamed:updated->date.lastModified")
    else:
        ctx.log("dropped_legacy_key_conflict:updated")


def struct_flatten_description(ctx, rec):
    """Flatten recognized English descriptions before optional-string cleanup."""
    description = rec.get("description")
    if not isinstance(description, dict):
        return
    english = description.get("en")
    if not isinstance(english, dict) or not any(
        key in english for key in ("shortDescription", "longDescription")
    ):
        ctx.log("skipped_flatten:description(no recognized English description)")
        return
    if "longDescription" in english:
        if is_empty(rec.get("longDescription")):
            rec["longDescription"] = english["longDescription"]
            ctx.log("hoisted:description.en.longDescription->longDescription")
        else:
            ctx.log("dropped_legacy_key_conflict:description.en.longDescription")
    if "shortDescription" in english:
        rec["description"] = english["shortDescription"]
        ctx.log("renamed:description.en.shortDescription->description")
    else:
        del rec["description"]
        ctx.log("omitted_missing:description.en.shortDescription")


def hoist_exemption_text(ctx, rec):
    """Top-level exemptionText belongs under permissions."""
    if "exemptionText" not in rec:
        return
    val = rec.pop("exemptionText")
    if is_empty(val):
        ctx.log("dropped_empty:exemptionText(top level)")
        return
    perms = rec.get("permissions")
    if perms is None:
        perms = rec["permissions"] = {}
    if not isinstance(perms, dict):
        rec["exemptionText"] = val
        ctx.log("skipped_hoist:exemptionText(permissions not an object)")
        return
    if is_empty(perms.get("exemptionText")):
        perms["exemptionText"] = val
        ctx.log("hoisted:exemptionText->permissions.exemptionText")
    else:
        ctx.log("dropped_legacy_key_conflict:exemptionText")


def struct_drop_legacy_usage_fields(ctx, rec):
    """Drop legacy project-type flags without changing permissions or usageType."""
    for field in ("openSourceProject", "governmentWideReuseProject"):
        if field in rec:
            rec.pop(field)
            ctx.log(f"dropped_legacy_field:{field}")


def struct_clean_required_strings(ctx, rec):
    for k in REQUIRED_STRINGS:
        if k not in rec:
            continue
        v = rec[k]
        if isinstance(v, str):
            s = v.strip()
            if s != v:
                ctx.log(f"trimmed:{k}")
            if not s:
                rec[k] = None
                ctx.log(f"empty_to_null:{k}")
            else:
                rec[k] = s
        elif v is not None:
            # Coerce non-string values to string
            try:
                s = str(v).strip()
                if s:
                    rec[k] = s
                    ctx.log(f"coerced_to_string:{k}")
                else:
                    rec[k] = None
                    ctx.log(f"empty_to_null_after_coerce:{k}")
            except Exception:
                rec[k] = None
                ctx.log(f"coercion_failed_to_null:{k}")
        else:
            # v is None, keep it as is
            pass


def struct_clean_optional_strings(ctx, rec):
    for k in OPTIONAL_STRINGS:
        if k not in rec:
            continue
        v = rec[k]
        if isinstance(v, str):
            s = v.strip()
            if s != v:
                ctx.log(f"trimmed:{k}")
            if s:
                rec[k] = s
            else:
                del rec[k]
                ctx.log(f"omitted_empty:{k}")
        elif v is None:
            del rec[k]
            ctx.log(f"omitted_empty:{k}")
        else:
            ctx.log(f"unexpected_type:{k}")


def struct_clean_version(ctx, rec):
    if "version" not in rec:
        return
    v = rec["version"]
    if isinstance(v, bool):
        ctx.log("unexpected_type:version")
    elif isinstance(v, (int, float)):
        rec["version"] = str(v)
        ctx.log("coerced_number_to_string:version")
    elif isinstance(v, str):
        s = v.strip()
        if s != v:
            ctx.log("trimmed:version")
        if s:
            rec["version"] = s
        else:
            del rec["version"]
            ctx.log("omitted_empty:version")
    elif v is None:
        del rec["version"]
        ctx.log("omitted_empty:version")
    else:
        ctx.log("unexpected_type:version")


def struct_clean_permissions(ctx, rec):
    perms = rec.get("permissions")
    if perms is None:
        return
    if not isinstance(perms, dict):
        ctx.log("unexpected_type:permissions")
        return
    strip_extra(ctx, perms, PERMISSIONS_KEYS, "permissions")

    if "licenses" in perms:
        lic = perms["licenses"]
        if lic is None:
            perms["licenses"] = []
            ctx.log("null_to_empty_list:permissions.licenses")
        else:
            if isinstance(lic, dict):
                lic = [lic]
                ctx.log("wrapped_object_in_list:permissions.licenses")
            if not isinstance(lic, list):
                ctx.log("unexpected_type:permissions.licenses")
            else:
                out = []
                for item in lic:
                    if not isinstance(item, dict):
                        ctx.log("dropped_non_object_item:permissions.licenses")
                        continue
                    strip_extra(ctx, item, LICENSE_KEYS, "permissions.licenses[]")
                    for k in LICENSE_KEYS:
                        if k in item:
                            trim_str(ctx, item, k, f"permissions.licenses[].{k}")
                            if is_empty(item[k]):
                                item[k] = None
                                ctx.log(f"empty_to_null:permissions.licenses[].{k}")
                    if all(is_empty(item.get(k)) for k in LICENSE_KEYS):
                        ctx.log("dropped_empty_item:permissions.licenses")
                        continue
                    out.append(item)
                perms["licenses"] = out

    if "usageType" in perms:
        ut = perms["usageType"]
        if ut is None:
            perms["usageType"] = []
            ctx.log("null_to_empty_list:permissions.usageType")
        else:
            out, _ = clean_str_list(ctx, ut, "permissions.usageType")
            if out is None:
                ctx.log("unexpected_type:permissions.usageType")
            else:
                perms["usageType"] = out

    if "exemptionText" in perms:
        v = perms["exemptionText"]
        if isinstance(v, str):
            s = v.strip()
            if s != v:
                ctx.log("trimmed:permissions.exemptionText")
            perms["exemptionText"] = s if s else None
            if not s:
                ctx.log("empty_to_null:permissions.exemptionText")
        elif v is not None:
            ctx.log("unexpected_type:permissions.exemptionText")


def struct_clean_reuse_frequency(ctx, rec):
    rf = rec.get("reuseFrequency")
    if rf is None:
        return
    if not isinstance(rf, dict):
        ctx.log("unexpected_type:reuseFrequency")
        return
    for k in ("forks", "clones", "downloads"):
        if k not in rf:
            continue
        v = rf[k]
        if v is None:
            del rf[k]
            ctx.log(f"omitted_empty:reuseFrequency.{k}")
            continue
        n = to_number(v)
        if n is None:
            del rf[k]
            ctx.log(f"omitted_non_numeric:reuseFrequency.{k}")
            continue
        if isinstance(n, float) and n.is_integer():
            n = int(n)
        if n != v or type(n) is not type(v):
            ctx.log(f"coerced_to_integer:reuseFrequency.{k}")
        rf[k] = n


def struct_clean_labor_hours(ctx, rec):
    if "laborHours" not in rec:
        return
    v = rec["laborHours"]
    n = to_number(v)
    if n is None:
        del rec["laborHours"]
        ctx.log("omitted_non_numeric:laborHours")
        return
    if isinstance(v, str):
        ctx.log("coerced_string_to_number:laborHours")
    rec["laborHours"] = n


def struct_clean_string_lists(ctx, rec):
    if "languages" in rec:
        v = rec["languages"]
        if v is None:
            del rec["languages"]
            ctx.log("omitted_empty:languages")
        else:
            out, _ = clean_str_list(ctx, v, "languages")
            if out is None:
                ctx.log("unexpected_type:languages")
            elif out:
                rec["languages"] = out
            else:
                del rec["languages"]
                ctx.log("omitted_empty:languages")

    if "tags" in rec:
        v = rec["tags"]
        if v is None:
            del rec["tags"]
            ctx.log("omitted_empty:tags")
        else:
            out, was_str = clean_str_list(ctx, v, "tags")
            if out is None:
                ctx.log("unexpected_type:tags")
            elif not out and was_str:
                del rec["tags"]
                ctx.log("omitted_empty:tags")
            else:
                rec["tags"] = out


def struct_clean_object_list(ctx, rec, key, allowed_keys):
    if key not in rec:
        return
    v = rec[key]
    if v is None:
        del rec[key]
        ctx.log(f"omitted_empty:{key}")
        return
    if isinstance(v, dict):
        v = [v]
        ctx.log(f"wrapped_object_in_list:{key}")
    if not isinstance(v, list):
        ctx.log(f"unexpected_type:{key}")
        return
    out = []
    for item in v:
        if not isinstance(item, dict):
            ctx.log(f"dropped_non_object_item:{key}")
            continue
        strip_extra(ctx, item, allowed_keys, f"{key}[]")
        for k in allowed_keys:
            if k in item:
                v = item[k]
                if isinstance(v, str):
                    s = v.strip()
                    if s != v:
                        ctx.log(f"trimmed:{key}[].{k}")
                    item[k] = s
                elif isinstance(v, bool) and k == "isGovernmentRepo":
                    pass
                elif v is not None:
                    ctx.log(f"unexpected_type:{key}[].{k}")
        if all(is_empty(item.get(k)) for k in allowed_keys):
            ctx.log(f"dropped_empty_item:{key}")
            continue
        out.append(item)
    if out:
        rec[key] = out
    else:
        del rec[key]
        ctx.log(f"omitted_empty:{key}")


def struct_clean_date(ctx, rec):
    if "date" not in rec:
        return
    dt = rec["date"]
    if dt is None or (isinstance(dt, list) and not dt):
        del rec["date"]
        ctx.log("omitted_empty:date")
        return
    if not isinstance(dt, dict):
        ctx.log("unexpected_type:date")
        return
    strip_extra(ctx, dt, DATE_KEYS, "date")
    for k in DATE_KEYS:
        if k in dt:
            trim_str(ctx, dt, k, f"date.{k}")
            if is_empty(dt[k]):
                del dt[k]
                ctx.log(f"omitted_empty:date.{k}")
    if not dt:
        del rec["date"]
        ctx.log("omitted_empty:date")


# --- value normalization (stage 3b) -----------------------------------------------

def squash(s):
    """Normalize whitespace: collapse multiple spaces."""
    return re.sub(r"\s+", " ", s.strip())


def parse_url(value):
    """Return SplitResult for a usable absolute URL, else None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s or re.search(r"\s", s):
        return None
    try:
        p = urlsplit(s)
    except ValueError:
        return None
    if not p.scheme or not p.netloc:
        # Try adding https:// prefix for URLs without scheme
        if not p.scheme and not p.netloc and p.path:
            try:
                p = urlsplit("https://" + s)
                if p.scheme and p.netloc:
                    return p
            except ValueError:
                pass
        return None
    return p


def upgrade_https(ctx, p, where):
    """http -> https, except when an explicit non-default port is present."""
    if p.scheme.lower() != "http":
        return p
    try:
        port = p.port
    except ValueError:
        port = -1  # malformed port: treat as custom, do not upgrade
    if port not in (None, 80, 443):
        ctx.log(f"https_upgrade_skipped_custom_port:{where}")
        return p
    netloc = p.netloc
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    ctx.log(f"http_to_https:{where}")
    return p._replace(scheme="https", netloc=netloc)


def value_clean_url_field(ctx, rec, key, required, where=None, container=None):
    """Validate + upgrade a URL field. Invalid -> null (required) / omitted (optional)."""
    d = container if container is not None else rec
    where = where or key
    if key not in d:
        return
    v = d[key]
    if v is None:
        return
    p = parse_url(v)
    if p is None:
        if required:
            d[key] = None
        else:
            del d[key]
        ctx.log(f"invalid_url_{'to_null' if required else 'omitted'}:{where}")
        return
    p = upgrade_https(ctx, p, where)
    new = urlunsplit(p)
    if new != v:
        d[key] = new


def is_bare_domain(p):
    return p.path in ("", "/") and not p.query and not p.fragment


def value_clean_repository_url(ctx, rec):
    if "repositoryURL" not in rec:
        return
    v = rec["repositoryURL"]
    if v is None:
        return
    if isinstance(v, str) and v.strip().lower() == "private":
        rec["repositoryURL"] = "private"
        return
    p = parse_url(v)
    if p is None:
        rec["repositoryURL"] = None
        ctx.log("invalid_url_to_null:repositoryURL")
        return

    if is_bare_domain(p):
        # A homepage, not a repository: move it, null the repository URL.
        if rec.get("homepageURL") in (None, ""):
            rec["homepageURL"] = urlunsplit(p)
            ctx.log("bare_domain_repositoryURL_moved_to_homepageURL")
        else:
            ctx.log("bare_domain_repositoryURL_nulled_homepage_kept")
        rec["repositoryURL"] = None
        return

    p = upgrade_https(ctx, p, "repositoryURL")
    path = p.path.rstrip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    path = path.rstrip("/")
    new = urlunsplit(p._replace(scheme=p.scheme.lower(),
                                netloc=p.netloc.lower(), path=path))
    if new != v:
        ctx.log("repositoryURL_canonicalized")
    rec["repositoryURL"] = new


def normalize_datetime(s):
    """Return (rfc3339 string or None, set of flags)."""
    s = s.strip()
    flags = set()
    m = SLASH_YMD.match(s)
    if m:
        s = "-".join(m.groups())
    m = DATE_RE.match(s)
    if not m:
        for fmt in TEXT_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%dT00:00:00Z"), {"date_only"}
            except ValueError:
                pass
        return None, flags
    y, mo, d, hh, mi, ss, frac, tz = m.groups()
    if hh is None:
        hh = mi = ss = "00"
        tz = "Z"
        flags.add("date_only")
    else:
        if ss is None:
            ss = "00"
            flags.add("added_seconds")
        if tz is None:
            tz = "Z"
            flags.add("assumed_utc")
    try:
        datetime(int(y), int(mo), int(d), int(hh), int(mi), int(ss))
    except ValueError:
        return None, set()
    if tz.lower() == "z":
        tz = "Z"
    else:
        digits = tz[1:].replace(":", "")
        tz = f"{tz[0]}{digits[:2]}:{digits[2:] or '00'}"
    return f"{y}-{mo}-{d}T{hh}:{mi}:{ss}{frac or ''}{tz}", flags


def value_clean_dates(ctx, rec):
    date = rec.get("date")
    if not isinstance(date, dict):
        return
    for k in list(date):
        v = date[k]
        if not isinstance(v, str):
            del date[k]
            ctx.log(f"date_non_string_omitted:{k}")
            continue
        new, flags = normalize_datetime(v)
        if new is None:
            del date[k]
            ctx.log(f"date_unparseable_omitted:{k}")
            continue
        for fl in flags:
            ctx.log(f"date_{fl}:{k}")
        date[k] = new
    if not date:
        del rec["date"]
        ctx.log("omitted_empty:date")


def value_clean_licenses(ctx, rec):
    perms = rec.get("permissions")
    if not isinstance(perms, dict) or not isinstance(perms.get("licenses"), list):
        return
    out = []
    for item in perms["licenses"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None:
            ctx.log("license_dropped_no_name")
            continue
        if not isinstance(name, str):
            ctx.log("license_dropped_non_string_name")
            continue
        if name in LICENSE_ENUM:
            new = name
        else:
            key = squash(name).lower()
            if key in LICENSE_MAP:
                new = LICENSE_MAP[key]
            else:
                new = "Other"
                ctx.log(f"license_unrecognized_to_Other")
        if new is None:
            ctx.log(f"license_dropped")
            continue
        if new != name:
            ctx.log(f"license_mapped")
        item["name"] = new
        value_clean_url_field(ctx, rec, "URL", required=True,
                        where="permissions.licenses[].URL", container=item)
        if item not in out:
            out.append(item)
    perms["licenses"] = out


def value_clean_usage_type(ctx, rec):
    perms = rec.get("permissions")
    if not isinstance(perms, dict) or not isinstance(perms.get("usageType"), list):
        return
    out = []
    for v in perms["usageType"]:
        canon = USAGE_LOOKUP.get(squash(v).lower()) if isinstance(v, str) else None
        if canon is None:
            ctx.log(f"usageType_unrecognized_dropped")
            continue
        if canon in USAGE_LEGACY:
            ctx.log(f"usageType_legacy_kept")
        elif canon != v:
            ctx.log(f"usageType_recased")
        if canon not in out:
            out.append(canon)
    perms["usageType"] = out


def value_clean_status(ctx, rec):
    v = rec.get("status")
    if not isinstance(v, str):
        return
    if v in STATUS_ENUM:
        return
    key = squash(v).lower()
    new = STATUS_MAP.get(key)
    if new is None:
        for prefix, mapped in STATUS_PREFIXES:
            if key.startswith(prefix):
                new = mapped
                break
    if new is None:
        rec["status"] = None
        ctx.log(f"status_unmapped_to_null")
    else:
        rec["status"] = new
        ctx.log(f"status_mapped")


def dedupe(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def value_clean_tags_and_lists(ctx, rec):
    if isinstance(rec.get("tags"), list):
        tags = []
        for t in rec["tags"]:
            if isinstance(t, str):
                t2 = squash(t).lower()
                if t2:
                    tags.append(t2)
        new = dedupe(tags)
        if new != rec["tags"]:
            ctx.log("tags_normalized")
        rec["tags"] = new
    for key in ("languages", "contractNumber"):
        if isinstance(rec.get(key), list):
            new = dedupe(rec[key])
            if len(new) != len(rec[key]):
                ctx.log(f"deduped:{key}")
            rec[key] = new


def value_clean_labor_hours(ctx, rec):
    v = rec.get("laborHours")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return
    if v == 0:
        del rec["laborHours"]
        ctx.log("laborHours_zero_omitted")
    elif v < 0:
        del rec["laborHours"]
        ctx.log("laborHours_negative_omitted")


def value_clean_contact_email(ctx, rec):
    c = rec.get("contact")
    if not isinstance(c, dict):
        return
    v = c.get("email")
    if isinstance(v, str) and not EMAIL_RE.match(v):
        c["email"] = None
        ctx.log("contact_email_malformed_to_null")

def value_clean_enum(ctx, rec, key, allowed, required):
    v = rec.get(key)
    if not isinstance(v, str):
        return
    low = v.strip().lower()
    if low in allowed:
        if low != v:
            ctx.log(f"lowercased:{key}")
        rec[key] = low
        return
    if required:
        rec[key] = None
        ctx.log(f"{key}_invalid_to_null")
    else:
        del rec[key]
        ctx.log(f"{key}_invalid_omitted")

def struct_clean_contact(ctx, rec):
    if "contact" not in rec:
        return
    c = rec["contact"]
    if c is None:
        del rec["contact"]
        ctx.log("omitted_empty:contact")
        return
    if not isinstance(c, dict):
        ctx.log("unexpected_type:contact")
        return
    strip_extra(ctx, c, CONTACT_KEYS, "contact")
    for k in CONTACT_KEYS:
        if k in c:
            trim_str(ctx, c, k, f"contact.{k}")
            if is_empty(c[k]):
                del c[k]
                ctx.log(f"empty_to_null:contact.{k}")
    if not c:
        del rec["contact"]
        ctx.log("omitted_empty:contact")

def apply_structural_normalization(ctx, rec):
    """Apply all structural normalization steps.
    
    Fixes the SHAPE of a record: renames legacy keys, hoists misplaced fields,
    strips forbidden nested keys, coerces types, trims strings, handles empty values.
    """
    if "" in rec:
        rec.pop("")
        ctx.log("dropped_top_level_key:<empty-string key>")

    rename_top_level(ctx, rec)
    rename_updated(ctx, rec)
    struct_flatten_description(ctx, rec)
    hoist_exemption_text(ctx, rec)
    struct_drop_legacy_usage_fields(ctx, rec)

    struct_clean_required_strings(ctx, rec)
    struct_clean_optional_strings(ctx, rec)
    struct_clean_version(ctx, rec)
    struct_clean_permissions(ctx, rec)
    struct_clean_reuse_frequency(ctx, rec)
    struct_clean_labor_hours(ctx, rec)
    struct_clean_string_lists(ctx, rec)
    struct_clean_object_list(ctx, rec, "relatedCode", RELATED_KEYS)
    struct_clean_object_list(ctx, rec, "reusedCode", REUSED_KEYS)
    struct_clean_object_list(ctx, rec, "partners", PARTNER_KEYS)
    struct_clean_date(ctx, rec)
    struct_clean_contact(ctx, rec)


def apply_value_normalization(ctx, rec):
    """Apply all value normalization steps.
    
    Normalizes VALUES: licenses, usageType, status, dates, URLs, tags, etc.
    Canonicalizes URLs, validates emails, enforces enums.
    """
    value_clean_repository_url(ctx, rec)  # may populate homepageURL, so run first
    value_clean_status(ctx, rec)
    value_clean_dates(ctx, rec)
    value_clean_licenses(ctx, rec)
    value_clean_usage_type(ctx, rec)
    value_clean_tags_and_lists(ctx, rec)
    value_clean_labor_hours(ctx, rec)
    value_clean_contact_email(ctx, rec)
    value_clean_enum(ctx, rec, "vcs", VCS_ENUM, required=False)
    value_clean_enum(ctx, rec, "repositoryVisibility", VISIBILITY_ENUM, required=True)
    value_clean_enum(ctx, rec, "maintenance", MAINTENANCE_ENUM, required=True)
    for key in ("homepageURL", "downloadURL", "disclaimerURL"):
        value_clean_url_field(ctx, rec, key, required=False)
    value_clean_url_field(ctx, rec, "feedbackMechanism", required=True)

def normalize_record(src, ctx=None):
    """Normalize a single project record.
    
    Applies structural normalization followed by value normalization.
    
    Returns normalized record after both stages.
    """
    if ctx is None:
        ctx = Ctx()

    rec = copy.deepcopy(src)

    # Apply structural normalization (stage 3a)
    apply_structural_normalization(ctx, rec)

    # Apply value normalization (stage 3b)
    apply_value_normalization(ctx, rec)

    return rec


def normalize_project(project):
    """Public API: Normalize a project dict. Returns normalized project.
    
    Args:
        project: Project dictionary to normalize
        
    Returns:
        Normalized project dictionary
    """
    ctx = Ctx()
    return normalize_record(project, ctx)
