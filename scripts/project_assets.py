"""Shared project identity, recency, and filesystem-safe write planning."""

from collections import defaultdict
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


def name_key(record):
    value = record.get("name")
    return (value.strip() or None) if isinstance(value, str) else None


def url_evidence(record):
    """Retain non-key URLs so different homepages/private markers cannot match."""
    return repository_key(record) or str(record.get("repositoryURL") or "").strip() or None


def resolve_incoming_duplicates(records, agency):
    """Resolve duplicate identities, warning and skipping unresolved groups."""
    groups = {}
    for position, record in enumerate(records, 1):
        if "govcode_id" in record:
            raise ValueError("Incoming govcode_id is reserved for local assignment")
        pair = (name_key(record), url_evidence(record))
        if not pair[0]:
            raise ValueError(f"[{agency}] Missing project name; review required: {record!r}")
        groups.setdefault(pair, []).append((position, record))

    resolved = []
    for pair, members in groups.items():
        # Canonical JSON ignores key order, but preserves JSON value types and
        # every source field. Do not merge fields from different versions.
        variants = {}
        for position, record in members:
            key = json.dumps(record, sort_keys=True, ensure_ascii=False)
            variants.setdefault(key, (position, record))
        unique = list(variants.values())
        chosen = unique[0]
        reason = "identical records collapsed"
        if len(unique) > 1:
            dated = [(latest_timestamp(record), position, record)
                     for position, record in unique]
            conflict = None
            if any(date is None for date, _, _ in dated):
                conflict = "conflicting records have missing/invalid timestamps"
            else:
                newest = max(date for date, _, _ in dated)
                winners = [(position, record) for date, position, record in dated if date == newest]
                if len(winners) != 1:
                    conflict = "conflicting records share the newest timestamp"
            if conflict:
                print(f"WARNING [{agency}]: skipped duplicate incoming identity {pair!r}: "
                      f"{conflict}; skipped releases {[position for position, _ in members]}; "
                      "existing record and ID retained if present; no new ID assigned; "
                      "resolve conflicting source code.json records",
                      file=sys.stderr, flush=True)
                continue
            chosen = winners[0]
            reason = f"kept uniquely newest record ({newest.isoformat()})"
        resolved.append(chosen[1])
        if len(members) > 1:
            print(f"WARNING [{agency}]: duplicate incoming identity {pair!r}: "
                  f"{reason}; kept release #{chosen[0]} of releases "
                  f"{[position for position, _ in members]}", file=sys.stderr, flush=True)
    return resolved


def plan_project_writes(index, agency_dir, *, identities=None, mappings=None):
    """Plan one-to-one matches without modifying files or incoming objects.

    IDs are allocated by save_projects after this entire plan succeeds.
    """
    incoming = resolve_incoming_duplicates(releases_from(index), agency_dir.name)
    if agency_dir.is_symlink():
        raise ValueError(f"Agency directory cannot be a symlink: {agency_dir}")
    existing = dict(identities or {})
    present = set()
    reserved = set(existing_name.casefold() for existing_name in existing)
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
            present.add(path.name)

    incoming_names = defaultdict(int)
    for record in incoming:
        incoming_names[name_key(record)] += 1

    by_name, by_url = defaultdict(list), defaultdict(list)
    for filename, old in existing.items():
        if name_key(old):
            by_name[name_key(old)].append(filename)
        if repository_key(old):
            by_url[repository_key(old)].append(filename)
    writes = {}
    claimed = set()
    for source in incoming:
        record = dict(source)
        if "govcode_id" in record:
            raise ValueError("Incoming govcode_id is reserved for local assignment")
        name, url = name_key(record), repository_key(record)
        same_name = by_name.get(name, [])
        same_url = by_url.get(url, [])
        matches = [f for f in same_name if f in same_url]
        if not matches and len(same_name) == 1 and incoming_names[name] == 1:
            old = existing[same_name[0]]
            if not url or not repository_key(old):
                a, b = url_evidence(record), url_evidence(old)
                if not a or not b or a == b:
                    matches = same_name
        overrides = [m for m in (mappings or [])
                     if m.get("name") == name and m.get("repositoryURL") == record.get("repositoryURL")]
        if overrides:
            if len(overrides) != 1 or overrides[0].get("filename") not in existing:
                raise ValueError(f"Invalid explicit mapping for {name!r}")
            matches = [overrides[0]["filename"]]
        if len(matches) > 1 or (not matches and (same_name or same_url)):
            raise ValueError(f"[{agency_dir.name}] Ambiguous match for {name!r} "
                             f"({record.get('repositoryURL')!r}): {same_name or same_url}; review required")
        if matches:
            filename = matches[0]
            if filename in claimed:
                raise ValueError(f"Multiple incoming records claim {filename}; review required")
            claimed.add(filename)
            old = existing[filename]
            incoming_date, old_date = latest_timestamp(record), latest_timestamp(old)
            if filename not in present or (incoming_date is not None and
                                          (old_date is None or incoming_date > old_date)):
                if "govcode_id" in old:
                    record["govcode_id"] = old["govcode_id"]
                writes[filename] = record
            elif incoming_date is None:
                print(f"WARNING [{agency_dir.name}]: {name!r} -> {filename!r}: "
                      "no recognized incoming timestamp; existing record retained", file=sys.stderr)
        else:
            filename = project_filename(record, agency_dir.name, reserved)
            writes[filename] = record
    return writes
