"""Tests for CSV export of nested project dates and numeric values."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.gov_code_to_csv import convert_to_csv


class CsvDateTests(unittest.TestCase):
    def test_numeric_zeros_are_preserved_in_csv(self):
        projects = [
            {"laborHours": value, "reuseFrequency": {
                "forks": value, "clones": value, "downloads": value,
            }}
            for value in (0, 7, None, "")
        ] + [{}, {"reuseFrequency": None}, {"reuseFrequency": {}}]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "output.csv"
            source.write_text(json.dumps([
                {"agency": "TEST", "releases": projects}
            ]), encoding="utf-8")
            self.assertTrue(convert_to_csv(source, output))
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            for column in ("laborHours", "reuseFrequency_forks",
                           "reuseFrequency_clones", "reuseFrequency_downloads"):
                with self.subTest(column=column):
                    self.assertEqual([row[column] for row in rows],
                                     ["0", "7", "", "", "", "", ""])

    def test_metadata_date_column_and_empty_values(self):
        timestamp = "2026-11-19T00:00:00Z"
        projects = [
            {"date": {"metadataLastUpdated": timestamp}},
            {},
            {"date": {}},
            {"date": None},
            {"date": {"metadataLastUpdated": None}},
            {"date": {"metadataLastUpdated": ""}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "output.csv"
            source.write_text(json.dumps([
                {"agency": "TEST", "releases": projects}
            ]), encoding="utf-8")
            self.assertTrue(convert_to_csv(source, output))
            with output.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns = reader.fieldnames
                self.assertEqual(
                    columns[columns.index("date_lastModified") + 1],
                    "date_metadataLastUpdated",
                )
                rows = list(reader)
            self.assertEqual(
                [row["date_metadataLastUpdated"] for row in rows],
                [timestamp, "", "", "", "", ""],
            )

    def test_local_id_is_first_column_and_value_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "output.csv"
            source.write_text(json.dumps([{"agency": "DOE", "releases": [
                {"name": "Example", "govcode_id": "2026-DOE-000123"},
                {"name": "Legacy"}]}]), encoding="utf-8")
            self.assertTrue(convert_to_csv(source, output))
            with output.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames[:3], ["govcode_id", "agency", "name"])
                self.assertEqual([row["govcode_id"] for row in reader], ["2026-DOE-000123", ""])
