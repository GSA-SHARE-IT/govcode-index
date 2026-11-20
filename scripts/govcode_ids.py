"""Persistent local IDs and recoverable project writes (Linux/macOS collectors)."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

if __package__:
    from .project_assets import plan_project_writes
else:
    from project_assets import plan_project_writes

ID_PATTERN = re.compile(r"[0-9]{4}-[A-Z0-9][A-Z0-9_]*-[0-9]{6,}")


def valid_id(value):
    return (isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None
            and int(value.rsplit("-", 1)[1]) > 0)


def atomic_json(path, value):
    """Publish a complete UTF-8 JSON file with an atomic same-directory rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing symlink: {path}")
    if isinstance(value, dict) and "govcode_id" in value:
        value = {"govcode_id": value["govcode_id"], **value}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".govcode-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=4, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def registry_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError(f"Refusing symlink: {directory}")
    lock = directory / ".lock"
    if lock.is_symlink():
        raise ValueError(f"Refusing symlink: {lock}")
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def check_filename(name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json"):
        raise ValueError(f"Unsafe registered filename: {name!r}")


def validate_registry(state):
    if (not isinstance(state, dict) or state.get("version") != 1
            or not isinstance(state.get("records"), dict)
            or not isinstance(state.get("pending"), dict)
            or type(state.get("next_number")) is not int or state["next_number"] < 1):
        raise ValueError("Invalid govcode registry")
    seen = set()
    numbers = set()
    for name, record in state["records"].items():
        check_filename(name)
        value = record.get("govcode_id") if isinstance(record, dict) else None
        if not valid_id(value) or value in seen:
            raise ValueError(f"Invalid or duplicate registered govcode_id: {name}")
        seen.add(value)
        number = int(value.rsplit("-", 1)[1])
        if number in numbers:
            raise ValueError("Registry reuses a sequence number")
        numbers.add(number)
        if int(value.rsplit("-", 1)[1]) >= state["next_number"]:
            raise ValueError("Registry counter would reuse an allocated number")
    for name, record in state["pending"].items():
        check_filename(name)
        if (not isinstance(record, dict) or name not in state["records"]
                or record.get("govcode_id") != state["records"][name]["govcode_id"]):
            raise ValueError(f"Invalid pending write: {name}")


def save_projects(index, agency_dir):
    """Allocate once, journal before writing, and replay interrupted writes."""
    agency = agency_dir.name.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_]*", agency):
        raise ValueError(f"Unsafe agency acronym: {agency!r}")
    if agency_dir.is_symlink():
        raise ValueError(f"Refusing symlink: {agency_dir}")
    directory = agency_dir.parent / ".govcode"
    with registry_lock(directory):
        path = directory / f"{agency}.json"
        if path.is_symlink():
            raise ValueError(f"Refusing symlink: {path}")
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "version": 1, "next_number": 1, "records": {}, "pending": {}}
        validate_registry(state)
        # A committed pending journal is sufficient to finish a partial write.
        for name, record in state["pending"].items():
            atomic_json(agency_dir / name, record)
        if state["pending"]:
            state["pending"] = {}
            atomic_json(path, state)
        for project in agency_dir.glob("*.json"):
            if project.is_symlink():
                raise ValueError(f"Refusing symlink: {project}")
            record = json.loads(project.read_text(encoding="utf-8"))
            registered = state["records"].get(project.name, {})
            if (not isinstance(record, dict) or not valid_id(record.get("govcode_id"))
                    or record.get("govcode_id") != registered.get("govcode_id")):
                raise ValueError(f"{project}: missing/unregistered govcode_id; "
                                 "use the planned staged rebuild before refreshing")
        mapping_path = directory / "matches.json"
        if mapping_path.is_symlink():
            raise ValueError(f"Refusing symlink: {mapping_path}")
        mappings = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
        if not isinstance(mappings, dict) or not isinstance(mappings.get(agency, []), list):
            raise ValueError("matches.json must map agency acronyms to lists")
        if any(not isinstance(item, dict) for item in mappings.get(agency, [])):
            raise ValueError("Each explicit match must be an object")
        writes = plan_project_writes(index, agency_dir, identities=state["records"],
                                    mappings=mappings.get(agency, []))
        for name, record in writes.items():
            if "govcode_id" not in record:
                record["govcode_id"] = (f"{datetime.now(timezone.utc).year}-{agency}-"
                                        f"{state['next_number']:06d}")
                state["next_number"] += 1
            state["records"][name] = {key: record[key] for key in
                                     ("name", "repositoryURL", "govcode_id") if key in record}
        if writes:
            state["pending"] = writes
            validate_registry(state)
            atomic_json(path, state)
            for name, record in writes.items():
                atomic_json(agency_dir / name, record)
            state["pending"] = {}
            atomic_json(path, state)
        agency_dir.mkdir(parents=True, exist_ok=True)
        return len(writes)
