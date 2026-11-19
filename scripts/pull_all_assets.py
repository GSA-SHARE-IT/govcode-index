"""Run both inventory collectors and report any incomplete refresh."""

import os
import sys

if __package__:
    from .pull_index_assets import pull_index_assets
    from .pull_public_assets import pull_public_assets
else:  # Direct execution: python scripts/pull_all_assets.py
    from pull_index_assets import pull_index_assets
    from pull_public_assets import pull_public_assets


def run_collector(collector):
    """Keep one collector's failure from preventing the other from running."""
    try:
        return collector()
    except Exception as exc:
        print(f"{collector.__name__} failed: {exc}", file=sys.stderr, flush=True)
        return 1


def main():
    index_status = run_collector(pull_index_assets)
    if os.getenv("GITHUB_TOKEN", "").strip():
        public_status = run_collector(pull_public_assets)
    else:
        print("Skipping public collection: GITHUB_TOKEN is missing. Configure the "
              "PUBLIC_ASSETS_TOKEN Actions secret.", file=sys.stderr, flush=True)
        public_status = 1
    return 1 if index_status or public_status else 0


if __name__ == "__main__":
    sys.exit(main())
