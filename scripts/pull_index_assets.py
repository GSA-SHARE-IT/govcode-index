"""Download the legacy agency indexes listed in sources/agency-index-sources.json."""

import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


try:
    from .project_assets import plan_project_writes
except ImportError:  # Direct script execution
    from project_assets import plan_project_writes


ROOT = Path(__file__).resolve().parent.parent


def save_projects(index, agency_dir):
    """Write new or newer projects, preserving existing filenames and records."""
    writes = plan_project_writes(index, agency_dir)
    agency_dir.mkdir(parents=True, exist_ok=True)
    for filename, project in writes.items():
        (agency_dir / filename).write_text(
            json.dumps(project, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return len(writes)


def pull_index_assets():
    """Collect inventories and return zero on success, or one on failure."""
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


def main():
    return pull_index_assets()


if __name__ == "__main__":
    sys.exit(main())
