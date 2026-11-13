"""Download the legacy agency indexes listed in sources/agency-index-sources.json."""

import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent


def save_projects(index, agency_dir):
    """Save each release intact, using filesystem-safe, unique project names."""

    if not isinstance(index, dict) or not isinstance(index.get("releases"), list):
        raise ValueError("Agency index must contain a releases array")
    releases = index["releases"]
    if any(not isinstance(project, dict) for project in releases):
        raise ValueError("Each release must be a project object")

    agency_dir.mkdir(parents=True, exist_ok=True)
    used_names = set()

    for project in releases:
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
                f"WARNING [{agency_dir.name}]: project {original_name!r} "
                f"-> {filename!r}: {'; '.join(reasons)}",
                file=sys.stderr,
                flush=True,
            )
        (agency_dir / filename).write_text(
            json.dumps(project, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return len(releases)


def main():
    sources = json.loads((ROOT / "sources/agency-index-sources.json").read_text())
    output_dir = ROOT / "agency-indexes"
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    for agency, url in sources.items():
        destination = output_dir / f"{agency}-index.json"

        # Download and process the agency index for the current agency
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "govcode-index/1.0 (public agency code inventory downloader)",
                    "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urlopen(request, timeout=30) as response:
                data = response.read()

            # Validate before writing so error pages cannot replace an index.
            try:
                index = json.loads(data)
            except UnicodeDecodeError:

                # Some legacy inventories contain Windows-1252 punctuation.
                legacy_text = data.decode("cp1252")
                index = json.loads(legacy_text)
                data = legacy_text.encode("utf-8")
                print(f"Converted {agency} from Windows-1252 to UTF-8", flush=True)

            # Saves the complete agency index to the $AGENCY-index.json file
            destination.write_bytes(data)

            # Writes each project to agency-indexes/$AGENCY/$PROJECT_NAME.json
            count = save_projects(index, output_dir / agency)
        
        except (URLError, OSError, ValueError) as exc:
            print(f"Failed {agency} ({url}): {exc}", file=sys.stderr)
            failures += 1
            continue

        print(f"Saved {destination.relative_to(ROOT)}", flush=True)
        print(f"Saved {count} projects in agency-indexes/{agency}/", flush=True)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
