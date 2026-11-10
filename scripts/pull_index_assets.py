"""Download the legacy agency indexes listed in sources/agency-index-sources.json."""

import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent


def main():
    sources = json.loads((ROOT / "sources/agency-index-sources.json").read_text())
    output_dir = ROOT / "agency-indexes"
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    for agency, url in sources.items():
        destination = output_dir / f"{agency}-index.json"
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
                json.loads(data)
            except UnicodeDecodeError:
                # Some legacy inventories contain Windows-1252 punctuation.
                legacy_text = data.decode("cp1252")
                json.loads(legacy_text)
                data = legacy_text.encode("utf-8")
                print(f"Converted {agency} from Windows-1252 to UTF-8", flush=True)
            destination.write_bytes(data)
        except (URLError, OSError, ValueError) as exc:
            print(f"Failed {agency} ({url}): {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"Saved {destination.relative_to(ROOT)}", flush=True)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
