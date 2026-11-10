"""Offline tests: python3 -m unittest discover -s tests -v."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import pull_index_assets as downloader


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "AGENCY"
        self.stderr = io.StringIO()
        self.enterContext(contextlib.redirect_stderr(self.stderr))

    def save(self, projects):
        return downloader.save_projects({"releases": projects}, self.directory)

    def test_preserves_complete_project_and_overwrites_on_rerun(self):
        project = {"name": "example", "description": "Café ®", "nested": {"tags": [1, None]}}
        self.assertEqual(self.save([project]), 1)
        path = self.directory / "example.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), project)
        project["description"] = "Updated"
        self.save([project])
        self.assertEqual(json.loads(path.read_text()), project)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_unsafe_name_stays_inside_agency_directory_and_is_flagged(self):
        project = {"name": '../folder\\project (one):?*|<>"\n'}
        self.save([project])
        files = list(self.directory.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text()), project)
        self.assertFalse(any(c in files[0].name for c in '/\\():?*|<>"\n '))
        warning = self.stderr.getvalue()
        self.assertIn("WARNING [AGENCY]", warning)
        self.assertIn(repr(project["name"]), warning)
        self.assertIn(repr(files[0].name), warning)
        self.assertIn("characters replaced or trimmed", warning)

    def test_collisions_do_not_drop_projects_including_case_and_suffix_collisions(self):
        projects = [{"name": name, "id": i} for i, name in enumerate(
            ["a/b", "a_b", "A_B", "a_b-2", "a/b"]
        )]
        self.save(projects)
        files = list(self.directory.glob("*.json"))
        self.assertEqual(len(files), len(projects))
        self.assertEqual(len({p.name.casefold() for p in files}), len(projects))
        self.assertEqual(sorted(json.loads(p.read_text())["id"] for p in files), list(range(5)))
        self.assertIn("duplicate filename", self.stderr.getvalue())

    def test_long_unicode_name_is_shortened_without_corrupting_content(self):
        project = {"name": "界" * 100}
        self.save([project])
        path, = self.directory.glob("*.json")
        self.assertLessEqual(len(path.stem.encode("utf-8")), 180)
        self.assertEqual(json.loads(path.read_text()), project)
        self.assertIn("truncated", self.stderr.getvalue())

    def test_missing_empty_and_dot_only_names_have_nonempty_unique_filenames(self):
        projects = [{}, {"name": ""}, {"name": None}, {"name": "..."}]
        self.save(projects)
        self.assertEqual(len(list(self.directory.glob("*.json"))), 4)
        self.assertTrue(all(p.stem for p in self.directory.glob("*.json")))
        self.assertIn("missing or empty project name", self.stderr.getvalue())

    def test_invalid_release_shapes_fail_before_writing(self):
        for index in [[], {}, {"releases": {}}, {"releases": [{"name": "ok"}, None]}]:
            with self.subTest(index=index), self.assertRaises(ValueError):
                downloader.save_projects(index, self.directory)
            self.assertFalse(self.directory.exists())

    def test_empty_index_creates_directory_without_projects(self):
        self.assertEqual(self.save([]), 0)
        self.assertEqual(list(self.directory.iterdir()), [])


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "sources").mkdir()
        self.enterContext(patch.object(downloader, "ROOT", self.root))
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.stdout))
        self.enterContext(contextlib.redirect_stderr(self.stderr))

    def run_download(self, responses):
        sources = {agency: f"https://example.test/{agency}.json" for agency in responses}
        (self.root / "sources/agency-index-sources.json").write_text(json.dumps(sources))

        def fetch(request, timeout):
            self.assertEqual(timeout, 30)
            self.assertIn("application/json", request.get_header("Accept"))
            self.assertTrue(request.get_header("User-agent"))
            agency = Path(request.full_url).stem
            response = responses[agency]
            if isinstance(response, Exception):
                raise response
            return io.BytesIO(response)

        with patch.object(downloader, "urlopen", side_effect=fetch):
            return downloader.main()

    def test_download_saves_full_index_and_project(self):
        project = {"name": "sample", "description": "café"}
        index = {"agency": "TEST", "releases": [project]}
        data = json.dumps(index, ensure_ascii=False).encode()
        self.assertEqual(self.run_download({"TEST": data}), 0)
        self.assertEqual((self.root / "agency-indexes/TEST-index.json").read_bytes(), data)
        self.assertEqual(json.loads((self.root / "agency-indexes/TEST/sample.json").read_text()), project)

    def test_windows_1252_is_saved_as_utf8(self):
        index = {"releases": [{"name": "sample", "description": "An en dash – and ®"}]}
        data = json.dumps(index, ensure_ascii=False).encode("cp1252")
        self.assertEqual(self.run_download({"TEST": data}), 0)
        saved = (self.root / "agency-indexes/TEST-index.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(saved), index)
        self.assertIn("Converted TEST from Windows-1252 to UTF-8", self.stdout.getvalue())

    def test_failures_preserve_existing_index_and_continue_to_next_agency(self):
        errors = [
            HTTPError("https://example.test", 403, "Forbidden", None, None),
            URLError("DNS failure"), TimeoutError("timed out"),
            b"<html>Access denied</html>", b'{"broken":',
        ]
        output = self.root / "agency-indexes"
        output.mkdir()
        existing = output / "BAD-index.json"
        for error in errors:
            with self.subTest(error=error):
                existing.write_text('{"previous": true}')
                self.assertEqual(self.run_download({"BAD": error, "GOOD": b'{"releases": []}'}), 1)
                self.assertEqual(existing.read_text(), '{"previous": true}')
                self.assertTrue((output / "GOOD-index.json").exists())
                self.assertIn("Failed BAD", self.stderr.getvalue())

    def test_missing_releases_reports_failure_and_continues(self):
        self.assertEqual(self.run_download({"BAD": b'{}', "GOOD": b'{"releases": []}'}), 1)
        self.assertIn("must contain a releases array", self.stderr.getvalue())
        self.assertTrue((self.root / "agency-indexes/GOOD").is_dir())


if __name__ == "__main__":
    unittest.main()
