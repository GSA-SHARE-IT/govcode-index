"""Offline ID lifecycle and identity ambiguity regressions."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import govcode_ids as ids
from scripts import project_assets as assets
from scripts import consolidate_to_gov_code as consolidation


def record(name="Example", url="https://github.com/org/repo", date="2025-01-01"):
    return {"name": name, "repositoryURL": url, "lastModified": date,
            "extra": {"unicode": "Café 界", "unknown": [None, 1]}}


class IdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.agency = self.root / "agency-indexes" / "DOE"
        self.registry = self.agency.parent / ".govcode" / "DOE.json"
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def save(self, *records):
        return ids.save_projects({"releases": list(records)}, self.agency)

    def read(self, name="Example.json"):
        return json.loads((self.agency / name).read_text())

    def test_assign_preserve_sequence_and_input_is_untouched(self):
        source = record()
        self.assertEqual(self.save(source), 1)
        first = self.read()
        self.assertEqual(next(iter(first)), "govcode_id")
        self.assertTrue(ids.valid_id(first["govcode_id"]))
        self.assertTrue(first["govcode_id"].endswith("-DOE-000001"))
        self.assertNotIn("govcode_id", source)
        self.assertEqual(self.save(source), 0)
        self.save(record(date="2026-01-01"))
        self.assertEqual(self.read()["govcode_id"], first["govcode_id"])
        self.save(record("Next", "https://github.com/org/next"))
        self.assertTrue(self.read("Next.json")["govcode_id"].endswith("000002"))

    def test_year_rollover_does_not_reset_sequence_or_ids(self):
        from datetime import datetime, timezone
        with patch.object(ids, "datetime") as clock:
            clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
            self.save(record())
            clock.now.return_value = datetime(2027, 1, 1, tzinfo=timezone.utc)
            self.save(record(date="2027-01-01"), record("New", "https://github.com/o/new"))
        self.assertEqual(self.read()["govcode_id"], "2026-DOE-000001")
        self.assertEqual(self.read("New.json")["govcode_id"], "2027-DOE-000002")

    def test_ambiguous_refresh_does_not_allocate_or_overwrite(self):
        self.save(record())
        before = self.registry.read_bytes()
        for candidate in (record("Renamed"), record(url="https://github.com/o/different")):
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                self.save(record("New", "https://github.com/o/new"), candidate)
            self.assertEqual(self.registry.read_bytes(), before)
            self.assertEqual(len(list(self.agency.glob("*.json"))), 1)

    def test_shared_catalog_matches_name_and_url_not_every_record(self):
        url = "https://example.gov/catalog"
        self.save(record("One", url), record("Two", url))
        old = self.read("Two.json")
        self.save(record("One", url, "2026-01-01"), record("Two", url))
        self.assertEqual(self.read("Two.json"), old)
        self.assertEqual(self.read("One.json")["lastModified"], "2026-01-01")

    def test_unique_name_fallback_and_conflicting_homepages(self):
        self.save(record(url=None))
        self.save(record(url=None, date="2026-01-01"))
        self.assertEqual(self.read()["lastModified"], "2026-01-01")
        # Missing URL may acquire a URL when the name remains unique.
        self.save(record(url="https://one.gov", date="2027-01-01"))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.save(record(url="https://two.gov", date="2028-01-01"))

    def test_duplicate_incoming_versions_keep_newest_and_one_id(self):
        import itertools
        from copy import deepcopy
        older = record(date="2024-01-01")
        newer = record(date="2026-01-01")
        newer["extra"]["new_field"] = "preserved"
        for batch in itertools.permutations([older, newer, deepcopy(newer)]):
            original = deepcopy(batch)
            warning = io.StringIO()
            with contextlib.redirect_stderr(warning):
                self.save(*batch)
            self.assertEqual(batch, original)
            saved = self.read()
            self.assertTrue(saved.pop("govcode_id").endswith("000001"))
            self.assertEqual(saved, newer)
            self.assertIn("uniquely newest", warning.getvalue())
        self.assertEqual(json.loads(self.registry.read_text())["next_number"], 2)

    def test_identical_undated_duplicates_collapse(self):
        first = record(date=None)
        second = dict(reversed(list(first.items())))
        warning = io.StringIO()
        with contextlib.redirect_stderr(warning):
            self.assertEqual(self.save(first, second), 1)
        self.assertIn("identical records collapsed", warning.getvalue())
        self.assertEqual(len(list(self.agency.glob("*.json"))), 1)

    def test_conflicting_duplicate_dates_skip_group_and_process_other_records(self):
        from copy import deepcopy
        for date in (None, "invalid", "2025-01-01", "2024-12-31T19:00:00-05:00"):
            for reverse in (False, True):
                other = record(date=date)
                other["extra"]["conflict"] = True
                batch = [record(), other]
                if reverse:
                    batch.reverse()
                with self.subTest(date=date, reverse=reverse):
                    before = deepcopy(batch)
                    warning = io.StringIO()
                    with contextlib.redirect_stderr(warning):
                        self.save(record("Unrelated", "https://github.com/o/other"), *batch)
                    self.assertEqual(batch, before)
                    self.assertFalse((self.agency / "Example.json").exists())
                    self.assertTrue(self.read("Unrelated.json")["govcode_id"].endswith("000001"))
                    self.assertEqual(json.loads(self.registry.read_text())["next_number"], 2)
                    self.assertIn("skipped duplicate incoming identity", warning.getvalue())
                    self.assertIn("resolve conflicting source code.json", warning.getvalue())

    def test_duplicate_resolution_preserves_existing_id_on_update(self):
        self.save(record())
        value = self.read()["govcode_id"]
        self.save(record(date="2024-01-01"), record(date="2026-01-01"))
        self.assertEqual(self.read()["govcode_id"], value)
        self.assertEqual(self.read()["lastModified"], "2026-01-01")

    def test_normalized_identity_deduplicates_but_does_not_merge_content(self):
        self.save(record(), record(" Example ", "https://GITHUB.com/ORG/REPO.git/", "2026-01-01"))
        self.assertEqual(self.read("_Example_.json")["name"], " Example ")
        self.assertEqual(self.read("_Example_.json")["repositoryURL"], "https://GITHUB.com/ORG/REPO.git/")

    def test_one_to_one_mapping_and_confirmed_rename(self):
        self.save(record())
        original_id = self.read()["govcode_id"]
        mapping = self.registry.parent / "matches.json"
        mapping.write_text(json.dumps({"DOE": [
            {"name": "Renamed", "repositoryURL": "https://github.com/org/repo",
             "filename": "Example.json"}]}))
        with self.assertRaisesRegex(ValueError, "Multiple incoming"):
            self.save(record(), record("Renamed", date="2026-01-01"))
        self.save(record("Renamed", date="2026-01-01"))
        self.assertEqual(self.read()["govcode_id"], original_id)
        self.assertEqual(self.read()["name"], "Renamed")
        self.assertFalse((self.agency / "Renamed.json").exists())

    def test_registry_retains_disappeared_identity_and_never_reuses_number(self):
        self.save(record())
        old = self.read()
        (self.agency / "Example.json").unlink()
        self.save(record("New", "https://github.com/o/new"))
        self.assertTrue(self.read("New.json")["govcode_id"].endswith("000002"))
        self.save(record())
        self.assertEqual(self.read()["govcode_id"], old["govcode_id"])

    def test_interrupted_write_replays_journal_without_new_ids(self):
        original = ids.atomic_json
        def fail_project(path, value):
            if path.parent == self.agency:
                raise OSError("simulated interruption")
            original(path, value)
        with patch.object(ids, "atomic_json", side_effect=fail_project):
            with self.assertRaises(OSError):
                self.save(record())
        state = json.loads(self.registry.read_text())
        allocated = state["pending"]["Example.json"]["govcode_id"]
        self.assertEqual(self.save(record()), 0)
        self.assertEqual(self.read()["govcode_id"], allocated)
        self.assertEqual(json.loads(self.registry.read_text())["pending"], {})

    def test_upstream_local_id_and_unregistered_existing_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.save({**record(), "govcode_id": "2026-DOE-123456"})
        self.agency.mkdir(parents=True)
        (self.agency / "Example.json").write_text(json.dumps(record()))
        with self.assertRaisesRegex(ValueError, "staged rebuild"):
            self.save(record())

    def test_matching_trims_name_and_normalizes_github_url(self):
        self.save(record())
        self.save(record(" Example ", "https://GITHUB.com/ORG/REPO.git/", "2026-01-01"))
        self.assertEqual(self.read()["name"], " Example ")
        self.assertEqual(len(list(self.agency.glob("*.json"))), 1)

    def test_agency_identifier_does_not_override_identity(self):
        self.save({**record(), "identifier": "same"})
        self.save({**record("Different", "https://github.com/o/other"), "identifier": "same"})
        self.assertNotEqual(self.read()["govcode_id"], self.read("Different.json")["govcode_id"])

    def test_corrupt_registry_rejected(self):
        self.save(record())
        state = json.loads(self.registry.read_text())
        state["next_number"] = 1
        self.registry.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "reuse"):
            self.save(record())

    def test_consolidation_preserves_ids_and_nulls_missing_identifier(self):
        self.save(record())
        with patch.object(consolidation, "VALID_AGENCIES", {"DOE"}, create=True), \
                patch.object(consolidation, "SCHEMA_VERSION", "1.0.0", create=True):
            result = consolidation.consolidate_indexes(self.root)
        release = result[0]["releases"][0]
        self.assertEqual(next(iter(release)), "govcode_id")
        self.assertEqual(release["govcode_id"], self.read()["govcode_id"])
        self.assertIsNone(release["identifier"])

    def test_consolidation_rejects_missing_duplicate_and_malformed_ids(self):
        self.save(record())
        original = self.read()
        with patch.object(consolidation, "VALID_AGENCIES", {"DOE"}, create=True):
            for value in (None, "invalid", "2026-DOE-000000"):
                (self.agency / "Example.json").write_text(json.dumps({**original, "govcode_id": value}))
                with self.assertRaisesRegex(ValueError, "invalid govcode_id"):
                    consolidation.consolidate_indexes(self.root)
            (self.agency / "Example.json").write_text(json.dumps(original))
            (self.agency / "Duplicate.json").write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "Duplicate govcode_id"):
                consolidation.consolidate_indexes(self.root)

    def test_legacy_identifier_mapping_and_local_id_survive(self):
        source = {**record(), "id": 123, "govcode_id": "2026-DOE-000001"}
        result = consolidation.normalize_project_file(source, "DOE", Path("test.json"))
        self.assertEqual(result["identifier"], "123")
        self.assertEqual(result["govcode_id"], source["govcode_id"])

    def test_name_only_fallback_requires_incoming_name_uniqueness(self):
        self.save(record(url=None))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.save(record(url="https://github.com/o/a"), record(url="https://github.com/o/b"))

    def test_local_release_schema_allows_null_identifier_and_requires_local_id(self):
        from scripts.utils.schema import validate_agency_index
        index = {"version": "1.0.0", "agency": "DOE", "releases": [
            {"govcode_id": "2026-DOE-000001", "identifier": None}]}
        self.assertTrue(validate_agency_index(index, "1.0.0", {"DOE"})[0])
        del index["releases"][0]["govcode_id"]
        self.assertFalse(validate_agency_index(index, "1.0.0", {"DOE"})[0])

    def test_consolidation_failure_does_not_publish(self):
        with patch.object(consolidation, "initialize_schema_config", return_value=("1", {"DOE"})), \
                patch.object(consolidation, "consolidate_indexes", side_effect=ValueError("invalid IDs")), \
                patch.object(consolidation, "save_gov_code_json") as publish:
            self.assertEqual(consolidation.main(), 1)
            publish.assert_not_called()

    def test_duplicate_existing_pair_is_not_updated_even_if_newer(self):
        self.save(record())
        original = self.read()
        (self.agency / "Copy.json").write_text(json.dumps({**original, "govcode_id": "2026-DOE-000002"}))
        state = json.loads(self.registry.read_text())
        state["records"]["Copy.json"] = {**original, "govcode_id": "2026-DOE-000002"}
        state["next_number"] = 3
        self.registry.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.save(record(date="2026-01-01"))
        self.assertEqual(self.read(), original)

    def test_consolidation_rejects_pending_transaction(self):
        self.save(record())
        state = json.loads(self.registry.read_text())
        state["pending"] = {"Example.json": self.read()}
        self.registry.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "incomplete collector transaction"):
            consolidation.consolidate_indexes(self.root)

    def test_symlinked_project_cannot_redirect_writes(self):
        self.save(record())
        target = self.root / "outside.json"
        target.write_text("unchanged")
        path = self.agency / "Example.json"
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.save(record(date="2026-01-01"))
        self.assertEqual(target.read_text(), "unchanged")

    def test_conflicting_duplicates_preserve_existing_bytes_and_registry(self):
        self.save(record(date="2024-01-01"))
        before = (self.agency / "Example.json").read_bytes()
        registry_before = self.registry.read_bytes()
        conflicting = {**record(), "description": "different"}
        self.assertEqual(self.save(record(), conflicting), 0)
        self.assertEqual((self.agency / "Example.json").read_bytes(), before)
        self.assertEqual(self.registry.read_bytes(), registry_before)

    def test_all_conflicted_new_records_allocate_nothing(self):
        self.assertEqual(self.save(record(), {**record(), "description": "different"}), 0)
        self.assertFalse(self.registry.exists())
        self.assertEqual(list(self.agency.glob("*.json")), [])
