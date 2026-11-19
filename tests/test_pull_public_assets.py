"""Offline public inventory tests; no installed generator or GitHub access needed."""

import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import pull_public_assets as public
from scripts import project_assets


def project(name="example", date=None, url="https://github.com/org/repo"):
    record = {"name": name, "repositoryURL": url, "extra": {"text": "Café 界"}}
    if date:
        record["date"] = {"lastModified": date}
    return record


def repository(name, record):
    content = SimpleNamespace(content=base64.b64encode(json.dumps(record).encode()))
    return SimpleNamespace(name=name, full_name=f"org/{name}", default_branch="main",
                           get_contents=Mock(return_value=content))


class FakeGenerator:
    """Implements the verified 1.1.0 API, including its misspelled keyword."""

    def __init__(self, agency, verison, token):
        self.index = {"agency": agency, "version": verison, "releases": []}
        self.github = Mock()

    def get_code_json(self, repo):
        return json.loads(base64.b64decode(repo.get_contents("code.json", ref=repo.default_branch).content))

    def update_index(self, index, record, org, name):
        index["releases"].append({"organization": org, "name": name, **record})

    def save_index(self, path):
        Path(path).write_text(json.dumps(self.index), encoding="utf-8")


class PublicTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "agency-indexes"
        self.agency = self.output / "TEST"
        self.stderr = io.StringIO()
        self.enterContext(contextlib.redirect_stderr(self.stderr))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def seed(self, name, record):
        self.agency.mkdir(parents=True, exist_ok=True)
        (self.agency / name).write_text(json.dumps(record), encoding="utf-8")

    def writes(self, records):
        return public.plan_project_writes({"releases": records}, self.agency)

    def factory(self, organizations):
        def create(**kwargs):
            generator = FakeGenerator(**kwargs)
            generator.github.get_organization.side_effect = lambda org: SimpleNamespace(
                get_repos=lambda **unused: iter(organizations[org]))
            return generator
        return Mock(side_effect=create)

    def test_latest_timestamp_fields_and_timezones(self):
        record = {"lastModified": "2023-01-01", "metadataLastUpdated": "bad",
                  "date": {"metadataLastUpdated": "2024-01-01T01:00:00+01:00",
                           "lastModified": "2024-01-02"}}
        self.assertEqual(project_assets.latest_timestamp(record).isoformat(), "2024-01-02T00:00:00+00:00")
        for field in project_assets.DATE_FIELDS:
            for nested in (True, False):
                with self.subTest(field=field, nested=nested):
                    value = {field: "2025-01-01T00:00:00Z"}
                    if nested:
                        value = {"date": value}
                    self.assertEqual(project_assets.latest_timestamp(value).year, 2025)
        for value in (None, 4, "", "invalid", "2024-99-01"):
            self.assertIsNone(project_assets.latest_timestamp({"lastModified": value}))

    def test_unused_metadata_spellings_do_not_affect_recency(self):
        for field in ("lastUpdatedMetadata", "lastMetadataUpdated"):
            for record in ({field: "2026-01-01"}, {"date": {field: "2026-01-01"}}):
                with self.subTest(record=record):
                    self.assertIsNone(project_assets.latest_timestamp(record))
                    record["lastModified"] = "2024-01-01"
                    self.assertEqual(project_assets.latest_timestamp(record).year, 2024)

    def test_newest_record_wins_and_filename_is_retained(self):
        old = project(date="2024-01-01")
        self.seed("original.json", old)
        for date, update in [("2025-01-01", True), ("2023-01-01", False),
                             ("2024-01-01", False), (None, False), ("bad", False),
                             ("2023-12-31T19:00:00-05:00", False)]:
            with self.subTest(date=date):
                new = project("renamed", date, "https://GITHUB.com/ORG/REPO.git/")
                self.assertEqual(self.writes([new]), {"original.json": new} if update else {})
        self.seed("original.json", project())
        self.assertEqual(self.writes([project(date="2024-01-01")]), {"original.json": old})

    def test_collision_warnings_preservation_and_repeat_stability(self):
        records = [project("a/b", url="https://github.com/o/1"),
                   project("A_B", url="https://github.com/o/2"),
                   project("界" * 100, url="https://github.com/o/3"),
                   {"unknown": [1, None]}, {"name": "../escape"}]
        self.seed("a_b.json", project(url="https://github.com/o/original"))
        writes = self.writes(records)
        self.assertEqual(len(writes), 5)
        self.assertNotIn("a_b.json", writes)
        self.assertEqual(len({name.casefold() for name in writes}), 5)
        for name, record in writes.items():
            self.assertEqual(Path(name).name, name)
            self.assertLessEqual(len(Path(name).stem.encode()), 182)
            self.seed(name, record)
        self.assertEqual(self.writes(records), {})
        for reason in ("duplicate filename", "truncated", "missing or empty", "characters replaced"):
            self.assertIn(reason, self.stderr.getvalue())
        for record in records:
            self.assertIn(repr(record.get("name")), self.stderr.getvalue())

    def test_missing_urls_only_match_identical_objects(self):
        self.seed("same.json", {"name": "same", "value": 1})
        self.assertEqual(self.writes([{"name": "same", "value": 1}]), {})
        self.assertEqual(list(self.writes([{"name": "same", "value": 2}])), ["same-2.json"])

    def test_duplicate_repository_candidates_use_newest_and_do_not_delete(self):
        self.seed("a.json", project(date="2024-01-01"))
        self.seed("b.json", project(date="2025-01-01"))
        self.assertEqual(self.writes([project(date="2024-06-01")]), {})
        newest = project(date="2026-01-01")
        self.assertEqual(self.writes([newest]), {"a.json": newest, "b.json": newest})

    def test_pagination_is_fully_consumed_and_duplicate_repositories_skipped(self):
        repos = [repository(str(i), project(str(i))) for i in range(101)]
        visited = []
        def pages():
            for page in (repos[:100], repos[100:]):
                visited.append(len(page))
                yield from page
        generator = FakeGenerator("TEST", "1.0.0", None)
        org = Mock()
        org.get_repos.side_effect = lambda **kwargs: pages()
        generator.github.get_organization.return_value = org
        public.collect_index(generator, ["org", "org"])
        self.assertEqual(len(generator.index["releases"]), 101)
        self.assertEqual(visited, [100, 1, 100, 1])
        org.get_repos.assert_called_with(type="public")
        for repo in repos:
            repo.get_contents.assert_called_once_with("code.json", ref="main")

    def test_missing_code_json_is_skipped_but_other_failures_propagate(self):
        repo = repository("missing", {})
        generator = self.factory({"org": [repo]})(agency="TEST", verison="1.0.0", token=None)
        for status in (404, 403, 429, 500):
            error = Exception("API failure")
            error.status = status
            repo.get_contents.side_effect = error
            if status == 404:
                public.collect_index(generator, ["org"])
                self.assertEqual(generator.index["releases"], [])
            else:
                with self.assertRaisesRegex(Exception, "API failure"):
                    public.collect_index(generator, ["org"])
        repo.get_contents.side_effect = None
        generator.get_code_json = Mock(return_value=None)
        with self.assertRaises(ValueError):
            public.collect_index(generator, ["org"])

    def test_staged_index_is_reloaded_and_index_named_project_is_safe(self):
        old = project("old", "2026-01-01")
        self.seed("old.json", old)
        raw = project("index", "2025-01-01", "https://github.com/org/index")
        factory = self.factory({"org": [repository("index", raw)]})
        public.process_agency("TEST", {"organizations": ["org"]}, self.output, "token", factory)
        factory.assert_called_once_with(agency="TEST", verison="1.0.0", token="token")
        saved = json.loads((self.output / "TEST-public-index.json").read_text())
        self.assertEqual(json.loads((self.agency / "index.json").read_text()), saved["releases"][0])
        self.assertEqual(json.loads((self.agency / "old.json").read_text()), old)
        self.assertIn("Café 界", (self.agency / "index.json").read_text())
        self.assertFalse(list(self.output.glob(".public-index-*")))

    def test_public_snapshot_can_be_older_than_project(self):
        old = project(date="2026-01-01")
        self.seed("example.json", old)
        factory = self.factory({"org": [repository("repo", project(date="2024-01-01"))]})
        public.process_agency("TEST", {"organizations": ["org"]}, self.output, None, factory)
        saved = json.loads((self.output / "TEST-public-index.json").read_text())
        self.assertEqual(saved["releases"][0]["date"]["lastModified"], "2024-01-01")
        self.assertEqual(json.loads((self.agency / "example.json").read_text()), old)

    def test_main_is_cwd_independent_and_continues_after_failure(self):
        sources = {"TEST": {"organizations": ["bad"]}, "NEXT": {"organizations": ["one", "two"]}}
        (self.root / "sources").mkdir()
        (self.root / "sources/public-sources.json").write_text(json.dumps(sources))
        self.seed("previous.json", {"keep": True})
        previous = self.output / "TEST-public-index.json"
        previous.write_text('{"previous": true}')
        factory = self.factory({"one": [repository("one", project())],
                                "two": [repository("two", project(url="https://github.com/org/two"))]})
        module = SimpleNamespace(IndexGenerator=factory)
        with patch.object(public, "ROOT", self.root), patch.dict("sys.modules", {"codejson_index_generator": module}):
            with contextlib.chdir(self.root / "sources"):
                self.assertEqual(public.main(), 1)
        self.assertEqual(previous.read_text(), '{"previous": true}')
        self.assertEqual(list(self.agency.iterdir()), [self.agency / "previous.json"])
        self.assertEqual(len(json.loads((self.output / "NEXT-public-index.json").read_text())["releases"]), 2)
        self.assertIn("Failed TEST", self.stderr.getvalue())

    def test_invalid_indexes_existing_files_and_unsafe_paths_do_not_publish(self):
        for index in ({}, {"releases": {}}, {"releases": [None]}):
            with self.assertRaises(ValueError):
                public.plan_project_writes(index, self.agency)
        factory = self.factory({"org": []})
        with self.assertRaises(ValueError):
            public.process_agency("../outside", {"organizations": ["org"]}, self.output, None, factory)
        self.seed("bad.json", {})
        (self.agency / "bad.json").write_text("invalid json")
        with self.assertRaises(ValueError):
            public.process_agency("TEST", {"organizations": ["org"]}, self.output, None, factory)
        self.assertFalse((self.output / "TEST-public-index.json").exists())

    def test_installed_generator_contract(self):
        try:
            from codejson_index_generator import IndexGenerator
        except ImportError:
            self.skipTest("Optional generator integration requires installed dependencies")
        generator = IndexGenerator(agency="TEST", verison="1.0.0", token=None)
        repo = repository("example", project(date="2024-01-01"))
        generator.github = Mock()
        generator.github.get_organization.return_value.get_repos.return_value = iter([repo])
        public.process_agency("TEST", {"organizations": ["org"]}, self.output, None,
                              lambda **kwargs: generator)
        saved = json.loads((self.output / "TEST-public-index.json").read_text())
        self.assertEqual(saved["version"], "1.0.0")
        self.assertEqual(saved["releases"][0],
                         {"organization": "org", **project(date="2024-01-01")})
        self.assertEqual(json.loads((self.agency / "example.json").read_text()),
                         saved["releases"][0])

    def test_inventory_wrappers_are_skipped_for_all_organizations(self):
        wrappers = [
            {"releases": [project("nested")]},
            {"name": "Source-Code-Inventory", "agency": "HHS", "releases": []},
            {"releases": None}, {"releases": [None]},
            {"projects": [project("nested")]}, {"projects": []},
            {"name": "inventory", "agency": "HHS", "projects": []},
            {"name": "inventory", "measurementType": {}, "projects": None},
        ]
        for org in ("HHS", "GSA", "18F"):
            for i, wrapper in enumerate(wrappers):
                with self.subTest(org=org, wrapper=wrapper):
                    output = self.output / org / str(i)
                    folder = output / org
                    folder.mkdir(parents=True)
                    existing = folder / "Source-Code-Inventory.json"
                    original = json.dumps(project("Source-Code-Inventory"))
                    existing.write_text(original)
                    ordinary = project("ordinary", "2025-01-01", "https://github.com/org/ordinary")
                    factory = self.factory({org: [
                        repository("Source-Code-Inventory", wrapper),
                        repository("ordinary", ordinary),
                    ]})
                    public.process_agency(org, {"organizations": [org]}, output, None, factory)
                    index = json.loads((output / f"{org}-public-index.json").read_text())
                    self.assertEqual(index["releases"], [{"organization": org, **ordinary}])
                    self.assertEqual({p.name for p in folder.iterdir()},
                                     {"Source-Code-Inventory.json", "ordinary.json"})
                    self.assertEqual(existing.read_text(), original)
        self.assertIn("org/Source-Code-Inventory/code.json", self.stderr.getvalue())
        self.assertIn("agency inventory, not an individual project", self.stderr.getvalue())

    def test_project_relationship_lists_are_preserved(self):
        records = [dict(project(f"record-{i}", url=f"https://github.com/org/{i}"), projects=value)
                   for i, value in enumerate(([], ["related-project"], ["https://github.com/org/related"]))]
        factory = self.factory({"GSA": [repository(r["name"], r) for r in records]})
        public.process_agency("GSA", {"organizations": ["GSA"]}, self.output, None, factory)
        index = json.loads((self.output / "GSA-public-index.json").read_text())
        self.assertEqual(index["releases"], [{"organization": "GSA", **r} for r in records])
        for record in index["releases"]:
            self.assertEqual(json.loads((self.output / "GSA" / (record["name"] + ".json")).read_text()), record)

    def test_symlinked_output_is_rejected(self):
        self.output.mkdir()
        self.agency.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            public.process_agency("TEST", {"organizations": []}, self.output, None, FakeGenerator)


if __name__ == "__main__":
    unittest.main()
