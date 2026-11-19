"""Collect public code.json inventories and retain the newest project records."""

import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace

try:
    from .project_assets import plan_project_writes, releases_from
except ImportError:  # Direct execution: python3 scripts/pull_public_assets.py
    from project_assets import plan_project_writes, releases_from


ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.0"


def organization_repositories(generator, organization):
    """Iterate PyGithub's lazy PaginatedList, including every public repo page."""
    yield from generator.github.get_organization(organization).get_repos(type="public")


def project_records(record, organization):
    """Unpack inventory wrappers only for the configured GSA organization."""
    if organization == "GSA":
        # Prefer the current schema when an inventory also includes legacy projects.
        field = next((key for key in ("releases", "projects") if key in record), None)
        if field is not None:
            projects = record[field]
            if not isinstance(projects, list) or any(not isinstance(item, dict) for item in projects):
                raise ValueError(f"GSA inventory {field} must be an array of project objects")
            return projects
    return [record]


def collect_index(generator, organizations):
    seen = set()
    for organization in organizations:
        for repository in organization_repositories(generator, organization):
            if repository.full_name.casefold() in seen:
                continue
            seen.add(repository.full_name.casefold())
            # The library swallows GitHub errors. Fetch once ourselves, distinguishing
            # missing files from failures, then let the library decode cached content.
            try:
                content = repository.get_contents("code.json", ref=repository.default_branch)
            except Exception as exc:
                if getattr(exc, "status", None) == 404:
                    continue
                raise
            cached_repository = SimpleNamespace(
                default_branch=repository.default_branch,
                get_contents=lambda *args, **kwargs: content,
            )
            record = generator.get_code_json(cached_repository)
            if not isinstance(record, dict):
                raise ValueError(f"Unable to retrieve a code.json object from {repository.full_name}")
            records = project_records(record, organization)
            for project in records:
                # Nested entries describe their own projects, not the inventory repo.
                fallback_name = repository.name if project is record else "unnamed-project"
                generator.update_index(generator.index, project, organization, fallback_name)


def process_agency(agency, configuration, output_dir, token, generator_factory):
    if not isinstance(agency, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", agency):
        raise ValueError(f"Unsafe agency directory name: {agency!r}")
    organizations = configuration.get("organizations") if isinstance(configuration, dict) else None
    if not isinstance(organizations, list) or any(
        not isinstance(org, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", org)
        for org in organizations
    ):
        raise ValueError("organizations must be a list of GitHub organization names")
    agency_dir = output_dir / agency
    if agency_dir.is_symlink():
        raise ValueError(f"Agency directory cannot be a symlink: {agency_dir}")
    # TODO: Correct spelling upstream
    generator = generator_factory(agency=agency, verison=VERSION, token=token)
    collect_index(generator, organizations)
    releases_from(generator.index)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Stage the library output, reload it, and resolve merges before publishing.
    with tempfile.TemporaryDirectory(dir=output_dir, prefix=".public-index-") as temporary:
        staging = Path(temporary)
        staged_index = staging / "index.json"
        generator.save_index(str(staged_index))
        index = json.loads(staged_index.read_text(encoding="utf-8"))
        writes = plan_project_writes(index, agency_dir)
        staged_projects = staging / "projects"
        staged_projects.mkdir()
        for name, record in writes.items():
            (staged_projects / name).write_text(
                json.dumps(record, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        agency_dir.mkdir(parents=True, exist_ok=True)
        for name in writes:
            (staged_projects / name).replace(agency_dir / name)
        destination = output_dir / f"{agency}-public-index.json"
        staged_index.replace(destination)
    print(f"Saved {destination}; updated {len(writes)} project files", flush=True)


def pull_public_assets():
    """Collect inventories and return zero on success, or one on failure."""
    try:
        from codejson_index_generator import IndexGenerator
    except ImportError:
        print("Install dependencies with: python3 -m pip install -r scripts/requirements.txt", file=sys.stderr)
        return 1
    try:
        sources = json.loads((ROOT / "sources/public-sources.json").read_text(encoding="utf-8"))
        if not isinstance(sources, dict):
            raise ValueError("Public sources must map agencies to organizations")
    except (OSError, ValueError) as exc:
        print(f"Failed to read public sources: {exc}", file=sys.stderr)
        return 1
    failures = 0
    for agency, configuration in sources.items():
        try:
            process_agency(agency, configuration, ROOT / "agency-indexes",
                           os.getenv("GITHUB_TOKEN"), IndexGenerator)
        except Exception as exc:
            print(f"Failed {agency}: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def main():
    return pull_public_assets()


if __name__ == "__main__":
    sys.exit(main())
