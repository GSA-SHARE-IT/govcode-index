"""Shared project identity, recency, and filesystem-safe write planning."""

from datetime import datetime, timezone
import json
import re
import sys
from urllib.parse import urlsplit

DATE_FIELDS = ("lastModified", "metadataLastUpdated")


def project_filename(project, agency, used_names):
    """Reserve a safe project filename and report any name changes."""
    # TODO: Consider stable project IDs for filenames after checking ID
    # coverage and uniqueness within each agency, with a fallback for missing IDs.
    reasons = []
    original_name = project.get("name")
    if not original_name:
        reasons.append("missing or empty project name")
    name = str(project.get("name") or "unnamed-project")
    stem = re.sub(r'[/\\()<>:"|?*\s\x00-\x1f]', "_", name).strip(". ")
    if stem != name:
        reasons.append("filename characters replaced or trimmed")

    # Leave room for a duplicate suffix and the extension on common filesystems.
    if len(stem.encode("utf-8")) > 180:
        reasons.append("name truncated to 180 UTF-8 bytes")
    stem = stem.encode("utf-8")[:180].decode("utf-8", errors="ignore")
    stem = stem or "unnamed-project"
    filename = f"{stem}.json"
    suffix = 2
    while filename.casefold() in used_names:
        filename = f"{stem}-{suffix}.json"
        suffix += 1
    if suffix > 2:
        reasons.append("duplicate filename (case-insensitive)")
    used_names.add(filename.casefold())
    if reasons:
        print(
            f"WARNING [{agency}]: project {original_name!r} "
            f"-> {filename!r}: {'; '.join(reasons)}",
            file=sys.stderr,
            flush=True,
        )
    return filename


def repository_key(record):
    value = record.get("repositoryURL")
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value.strip())
        if url.scheme not in ("http", "https") or not url.hostname or not url.path.strip("/"):
            return None
        path = url.path.rstrip("/")
        if url.hostname.lower() == "github.com":
            path = path.casefold()
            if path.endswith(".git"):
                path = path[:-4]
        return (url.hostname.lower(), url.port, path)
    except ValueError:
        return None


def latest_timestamp(record):
    values = []
    containers = [record]
    if isinstance(record.get("date"), dict):
        containers.append(record["date"])
    for container in containers:
        for field in DATE_FIELDS:
            value = container.get(field)
            if not isinstance(value, str):
                continue
            try:
                timestamp = datetime.fromisoformat(value)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                values.append(timestamp.astimezone(timezone.utc))
            except (ValueError, OverflowError):
                continue
    return max(values, default=None)


def releases_from(index):
    if not isinstance(index, dict) or not isinstance(index.get("releases"), list):
        raise ValueError("Agency index must contain a releases array")
    if any(not isinstance(record, dict) for record in index["releases"]):
        raise ValueError("Each release must be a project object")
    return index["releases"]


def plan_project_writes(index, agency_dir):
    """Resolve all matches before writing; existing records and filenames survive."""
    incoming = releases_from(index)
    if agency_dir.is_symlink():
        raise ValueError(f"Agency directory cannot be a symlink: {agency_dir}")
    existing = {}
    reserved = set()
    if agency_dir.exists():
        for path in sorted(agency_dir.iterdir()):
            reserved.add(path.name.casefold())
            if path.suffix.lower() != ".json":
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Expected a regular project file: {path}")
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError(f"Expected a project object: {path}")
            existing[path.name] = record

    writes = {}
    for record in incoming:
        key = repository_key(record)
        matches = [name for name, old in existing.items()
                   if (repository_key(old) == key if key else old == record)]
        if matches:
            # If historical duplicates exist, compare against their newest version.
            newest = max((latest_timestamp(existing[name]) for name in matches),
                         key=lambda date: date or datetime.min.replace(tzinfo=timezone.utc))
            incoming_date = latest_timestamp(record)
            if incoming_date is not None and (newest is None or incoming_date > newest):
                for name in matches:
                    existing[name] = record
                    writes[name] = record
        else:
            name = project_filename(record, agency_dir.name, reserved)
            existing[name] = record
            writes[name] = record
    return writes


