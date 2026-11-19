"""Offline orchestration and cross-source merge regressions."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import pull_all_assets as runner
from scripts import pull_index_assets as legacy
from scripts import pull_public_assets as public


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.enterContext(patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}))

    def test_status_combinations_always_attempt_both_in_order(self):
        for statuses in ((0, 0), (1, 0), (0, 1), (1, 1)):
            order = []
            def index():
                order.append("index")
                return statuses[0]
            def public_collector():
                order.append("public")
                return statuses[1]
            with self.subTest(statuses=statuses), patch.object(runner, "pull_index_assets", index), \
                    patch.object(runner, "pull_public_assets", public_collector):
                self.assertEqual(runner.main(), int(any(statuses)))
                self.assertEqual(order, ["index", "public"])

    def test_missing_token_runs_legacy_and_reports_failure(self):
        for token in ("", "   "):
            with patch.dict("os.environ", {"GITHUB_TOKEN": token}), \
                    patch.object(runner, "pull_index_assets", return_value=0) as index, \
                    patch.object(runner, "pull_public_assets") as public_collector:
                self.assertEqual(runner.main(), 1)
                index.assert_called_once_with()
                public_collector.assert_not_called()
        self.assertIn("PUBLIC_ASSETS_TOKEN", self.stderr.getvalue())

    def test_exception_does_not_skip_second_collector(self):
        def broken():
            raise ValueError("invalid source configuration")
        with patch.object(runner, "pull_index_assets", broken), \
                patch.object(runner, "pull_public_assets", return_value=0) as public_collector:
            self.assertEqual(runner.main(), 1)
            public_collector.assert_called_once_with()
        self.assertIn("invalid source configuration", self.stderr.getvalue())

    def test_paths_are_independent_of_callers_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sources").mkdir()
            (root / "sources/agency-index-sources.json").write_text("{}")
            (root / "sources/public-sources.json").write_text("{}")
            from types import SimpleNamespace
            with contextlib.chdir(root / "sources"), \
                    patch.object(legacy, "ROOT", root), patch.object(public, "ROOT", root), \
                    patch.dict("sys.modules", {"codejson_index_generator": SimpleNamespace(IndexGenerator=object)}):
                self.assertEqual(runner.main(), 0)
                self.assertTrue((root / "agency-indexes").is_dir())

    def test_standalone_main_delegates_to_importable_function(self):
        for module, name in ((legacy, "pull_index_assets"), (public, "pull_public_assets")):
            with self.subTest(name=name), patch.object(module, name, return_value=1) as collector:
                self.assertEqual(module.main(), 1)
                collector.assert_called_once_with()


class CrossSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "TEST"
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def save(self, source, record):
        index = {"releases": [record]}
        if source == "legacy":
            return legacy.save_projects(index, self.directory)
        writes = public.plan_project_writes(index, self.directory)
        self.directory.mkdir(exist_ok=True)
        for name, value in writes.items():
            (self.directory / name).write_text(json.dumps(value), encoding="utf-8")
        return len(writes)

    def test_both_source_orders_keep_newest_with_original_filename(self):
        for first, second in (("public", "legacy"), ("legacy", "public")):
            with self.subTest(first=first):
                self.directory = self.directory.parent / first
                initial = {"name": "original", "repositoryURL": "https://github.com/Org/Repo.git/",
                           "date": {"lastModified": "2024-01-01"}, "unknown": ["café", None]}
                self.assertEqual(self.save(first, initial), 1)
                for date in ("2023-01-01", "2024-01-01", "invalid", None):
                    incoming = {**initial, "name": "renamed", "repositoryURL": "https://github.com/org/repo",
                                "date": {"lastModified": date}}
                    self.assertEqual(self.save(second, incoming), 0)
                incoming["date"] = {"metadataLastUpdated": "2025-01-01"}
                self.assertEqual(self.save(second, incoming), 1)
                path = self.directory / "original.json"
                self.assertEqual(json.loads(path.read_text()), incoming)
                self.assertEqual(list(self.directory.iterdir()), [path])
                self.assertEqual(self.save(first, initial), 0)

    def test_missing_dates_and_distinct_same_name_repositories(self):
        initial = {"name": "same", "repositoryURL": "https://github.com/o/a"}
        self.assertEqual(self.save("legacy", initial), 1)
        self.assertEqual(self.save("public", {**initial, "extra": "no timestamp"}), 0)
        newer = {**initial, "metadataLastUpdated": "2025-01-01"}
        self.assertEqual(self.save("public", newer), 1)
        self.assertEqual(self.save("legacy", {**newer, "repositoryURL": "https://github.com/o/b"}), 1)
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"same.json", "same-2.json"})

    def test_url_less_records_only_match_identical_objects(self):
        self.assertEqual(self.save("legacy", {"name": "same"}), 1)
        self.assertEqual(self.save("public", {"name": "same"}), 0)
        self.assertEqual(self.save("legacy", {"name": "same", "extra": True}), 1)
        self.assertEqual(len(list(self.directory.iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
