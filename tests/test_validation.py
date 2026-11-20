"""Validation and filling tests for code.json project records.

Tests for scripts/utils/validate.py:
- Helper functions (URL validation, identifiers, closing logic)
- Validation pipeline (validate_record)
- Filling pipeline (fill_record, standardization)
- Integration tests
"""

import unittest
from scripts.utils.validate import (
    slugify, usable_url, is_github_repo, github_repo,
    is_closed, standardize_license_name, standardize_status,
    validate_record, has_identity, fill_record
)


class DateContainerValidationTests(unittest.TestCase):
    def test_non_object_dates_report_errors_without_mutating_records(self):
        from copy import deepcopy
        for value in ([], [""], ["2025-04-08"], ["", "2025-04-08"],
                      [{}], [0], [False], "2025-04-08", 0, False):
            with self.subTest(value=value):
                record = {"date": value}
                original = deepcopy(record)
                valid, errors, _ = validate_record(record)
                self.assertTrue(valid)  # Existing non-blocking contract.
                self.assertEqual([error for error in errors if "Field 'date'" in error],
                                 ["Field 'date' must be object or null"])
                self.assertEqual(record, original)

    def test_normalized_placeholders_and_date_objects_have_no_container_error(self):
        from scripts.utils.normalize import normalize_project
        for record in ({}, {"date": None}, {"date": {}}, {"date": {"created": "2025-04-08T00:00:00Z"}},
                       normalize_project({"date": ["", None, " "]})):
            with self.subTest(record=record):
                _, errors, _ = validate_record(record)
                self.assertFalse(any("Field 'date'" in error for error in errors))


class HelperFunctionTests(unittest.TestCase):
    """Tests for helper functions."""

    # === slugify ===
    def test_slugify_converts_to_kebab_case(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_slugify_removes_special_chars(self):
        self.assertEqual(slugify("Test_Project!@#$"), "test-project")

    def test_slugify_limits_to_40_chars(self):
        long_name = "a" * 50
        result = slugify(long_name)
        self.assertEqual(len(result), 40)

    def test_slugify_empty_string_becomes_unnamed(self):
        self.assertEqual(slugify(""), "unnamed")

    def test_slugify_handles_non_string_input(self):
        self.assertEqual(slugify(123), "123")

    # === usable_url ===
    def test_usable_url_accepts_https_url(self):
        self.assertTrue(usable_url("https://github.com/test/repo"))

    def test_usable_url_accepts_http_url(self):
        self.assertTrue(usable_url("http://example.com/path"))

    def test_usable_url_rejects_non_string(self):
        self.assertFalse(usable_url(123))
        self.assertFalse(usable_url(None))
        self.assertFalse(usable_url(["url"]))

    def test_usable_url_rejects_empty_string(self):
        self.assertFalse(usable_url(""))

    def test_usable_url_rejects_private_string(self):
        self.assertFalse(usable_url("private"))

    def test_usable_url_case_insensitive_private(self):
        self.assertFalse(usable_url("PRIVATE"))
        self.assertFalse(usable_url("Private"))

    def test_usable_url_rejects_invalid_schemes(self):
        self.assertFalse(usable_url("ftp://example.com"))
        self.assertFalse(usable_url("file:///path/to/file"))

    def test_usable_url_requires_netloc(self):
        self.assertFalse(usable_url("https://"))

    # === is_github_repo ===
    def test_is_github_repo_github_com(self):
        self.assertTrue(is_github_repo("https://github.com/owner/repo"))

    def test_is_github_repo_www_github_com(self):
        self.assertTrue(is_github_repo("https://www.github.com/owner/repo"))

    def test_is_github_repo_case_insensitive(self):
        self.assertTrue(is_github_repo("HTTPS://GITHUB.COM/OWNER/REPO"))
        self.assertTrue(is_github_repo("https://GitHub.Com/owner/repo"))

    def test_is_github_repo_non_github_url(self):
        self.assertFalse(is_github_repo("https://gitlab.com/owner/repo"))
        self.assertFalse(is_github_repo("https://bitbucket.org/owner/repo"))

    def test_is_github_repo_non_url_input(self):
        self.assertFalse(is_github_repo("not a url"))
        self.assertFalse(is_github_repo(""))
        self.assertFalse(is_github_repo(None))

    # === github_repo ===
    def test_github_repo_extracts_owner_and_repo(self):
        result = github_repo("https://github.com/owner/repo")
        self.assertEqual(result, ("owner", "repo"))

    def test_github_repo_removes_git_suffix(self):
        result = github_repo("https://github.com/owner/repo.git")
        self.assertEqual(result, ("owner", "repo"))

    def test_github_repo_handles_trailing_slash(self):
        result = github_repo("https://github.com/owner/repo/")
        self.assertEqual(result, ("owner", "repo"))

    def test_github_repo_handles_git_and_trailing_slash(self):
        result = github_repo("https://github.com/owner/repo.git/")
        self.assertEqual(result, ("owner", "repo"))

    def test_github_repo_non_github_url_returns_none(self):
        self.assertIsNone(github_repo("https://gitlab.com/owner/repo"))

    def test_github_repo_invalid_url_returns_none(self):
        self.assertIsNone(github_repo("not a url"))

    def test_github_repo_url_too_few_parts_returns_none(self):
        self.assertIsNone(github_repo("https://github.com/owner"))

    # === is_closed ===
    def test_is_closed_with_exempt_usage_no_opensource(self):
        record = {
            "permissions": {
                "usageType": ["exemptByNationalSecurity"]
            }
        }
        self.assertTrue(is_closed(record))

    def test_is_closed_with_opensource_in_usage(self):
        record = {
            "permissions": {
                "usageType": ["openSource", "exemptByNationalSecurity"]
            }
        }
        self.assertFalse(is_closed(record))

    def test_is_closed_no_exempt_usage(self):
        record = {
            "permissions": {
                "usageType": ["openSource"]
            }
        }
        self.assertFalse(is_closed(record))

    def test_is_closed_permissions_not_dict(self):
        record = {"permissions": "invalid"}
        self.assertFalse(is_closed(record))

    def test_is_closed_no_permissions(self):
        record = {}
        self.assertFalse(is_closed(record))


if __name__ == "__main__":
    unittest.main()


class StandardizationTests(unittest.TestCase):
    """Tests for standardize_license_name and standardize_status."""

    # === standardize_license_name ===
    def test_standardize_license_mit_lowercase(self):
        result, was_mapped = standardize_license_name("mit")
        self.assertEqual(result, "MIT")
        self.assertTrue(was_mapped)

    def test_standardize_license_mit_with_text(self):
        result, was_mapped = standardize_license_name("mit license")
        self.assertEqual(result, "MIT")
        self.assertTrue(was_mapped)

    def test_standardize_license_apache(self):
        result, was_mapped = standardize_license_name("apache-2.0")
        self.assertEqual(result, "Apache-2.0")
        self.assertTrue(was_mapped)

    def test_standardize_license_apache_verbose(self):
        result, was_mapped = standardize_license_name("Apache License 2.0")
        self.assertEqual(result, "Apache-2.0")
        self.assertTrue(was_mapped)

    def test_standardize_license_public_domain(self):
        result, was_mapped = standardize_license_name("public domain")
        self.assertEqual(result, "CC0-1.0")
        self.assertTrue(was_mapped)

    def test_standardize_license_gpl2(self):
        result, was_mapped = standardize_license_name("gpl2")
        self.assertEqual(result, "GPL-2.0-only")
        self.assertTrue(was_mapped)

    def test_standardize_license_gpl3(self):
        result, was_mapped = standardize_license_name("gpl-3.0-or-later")
        self.assertEqual(result, "GPL-3.0-or-later")
        self.assertTrue(was_mapped)

    def test_standardize_license_bsd3(self):
        result, was_mapped = standardize_license_name('bsd 3-clause "new" or "revised" license')
        self.assertEqual(result, "BSD-3-Clause")
        self.assertTrue(was_mapped)

    def test_standardize_license_none(self):
        result, was_mapped = standardize_license_name("none")
        self.assertEqual(result, "None")
        self.assertTrue(was_mapped)

    def test_standardize_license_noassertion_returns_none(self):
        result, was_mapped = standardize_license_name("noassertion")
        self.assertIsNone(result)
        self.assertTrue(was_mapped)

    def test_standardize_license_unmappable(self):
        result, was_mapped = standardize_license_name("custom-license")
        self.assertEqual(result, "custom-license")
        self.assertFalse(was_mapped)

    def test_standardize_license_case_insensitive(self):
        result, was_mapped = standardize_license_name("MIT LICENSE")
        self.assertEqual(result, "MIT")
        self.assertTrue(was_mapped)

    def test_standardize_license_with_whitespace(self):
        result, was_mapped = standardize_license_name("  mit  ")
        self.assertEqual(result, "MIT")
        self.assertTrue(was_mapped)

    def test_standardize_license_none_input(self):
        result, was_mapped = standardize_license_name(None)
        self.assertIsNone(result)
        self.assertFalse(was_mapped)

    # === standardize_status ===
    def test_standardize_status_exact_match(self):
        result, was_mapped = standardize_status("Alpha")
        self.assertEqual(result, "Alpha")
        self.assertTrue(was_mapped)

    def test_standardize_status_lowercase(self):
        result, was_mapped = standardize_status("alpha")
        self.assertEqual(result, "Alpha")
        self.assertTrue(was_mapped)

    def test_standardize_status_development(self):
        result, was_mapped = standardize_status("development")
        self.assertEqual(result, "Development")
        self.assertTrue(was_mapped)

    def test_standardize_status_production(self):
        result, was_mapped = standardize_status("production")
        self.assertEqual(result, "Production")
        self.assertTrue(was_mapped)

    def test_standardize_status_archival(self):
        result, was_mapped = standardize_status("archival")
        self.assertEqual(result, "Archival")
        self.assertTrue(was_mapped)

    def test_standardize_status_release_candidate(self):
        result, was_mapped = standardize_status("release candidate")
        self.assertEqual(result, "Release Candidate")
        self.assertTrue(was_mapped)

    def test_standardize_status_rc_abbrev(self):
        result, was_mapped = standardize_status("rc")
        self.assertEqual(result, "Release Candidate")
        self.assertTrue(was_mapped)

    def test_standardize_status_release_candidate_hyphen(self):
        result, was_mapped = standardize_status("release-candidate")
        self.assertEqual(result, "Release Candidate")
        self.assertTrue(was_mapped)

    def test_standardize_status_prefix_match_alpha_prefix(self):
        result, was_mapped = standardize_status("alpha 1.0")
        self.assertEqual(result, "Alpha")
        self.assertTrue(was_mapped)

    def test_standardize_status_prefix_match_beta_prefix(self):
        result, was_mapped = standardize_status("beta testing")
        self.assertEqual(result, "Beta")
        self.assertTrue(was_mapped)

    def test_standardize_status_unmappable(self):
        result, was_mapped = standardize_status("experimental")
        self.assertEqual(result, "experimental")
        self.assertFalse(was_mapped)

    def test_standardize_status_none_input(self):
        result, was_mapped = standardize_status(None)
        self.assertIsNone(result)
        self.assertFalse(was_mapped)


if __name__ == "__main__":
    unittest.main()


class ValidateRecordTests(unittest.TestCase):
    """Tests for validate_record function."""

    def test_validate_valid_complete_record(self):
        """Complete valid record should pass validation."""
        record = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "permissions": {
                "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}],
                "usageType": ["openSource"]
            },
            "reuseFrequency": {},
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://github.com/test/repo/issues"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_not_a_dict(self):
        """Non-dict input should produce error."""
        is_valid, errors, warnings = validate_record("not a dict")
        self.assertFalse(is_valid)  # Non-dict causes is_valid to be False
        self.assertIn("Record must be a JSON object", errors[0])

    def test_validate_missing_required_field(self):
        """Missing required field should produce error."""
        record = {"name": "Test"}  # missing other required fields
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("Missing required field" in e for e in errors))

    def test_validate_missing_all_required_fields(self):
        """All required fields missing should produce multiple errors."""
        record = {}
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertGreater(len(errors), 10)  # 13 required fields

    def test_validate_name_wrong_type(self):
        """Name as non-string should produce error."""
        record = {
            "name": 123,
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {"licenses": [], "usageType": []},
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("name" in e and "must be string" in e for e in errors))

    def test_validate_permissions_not_dict(self):
        """Permissions as non-dict should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": "invalid",
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("permissions" in e and "must be object" in e for e in errors))

    def test_validate_missing_permissions_licenses(self):
        """Missing licenses in permissions should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {"usageType": []},
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("licenses" in e and "required" in e for e in errors))

    def test_validate_missing_permissions_usageType(self):
        """Missing usageType in permissions should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {"licenses": []},
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("usageType" in e and "required" in e for e in errors))

    def test_validate_license_missing_name(self):
        """License item missing name should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {
                "licenses": [{"URL": "https://opensource.org/licenses/MIT"}],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("licenses[0].name" in e and "required" in e for e in errors))

    def test_validate_license_missing_url(self):
        """License item missing URL should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {
                "licenses": [{"name": "MIT"}],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("licenses[0].URL" in e and "required" in e for e in errors))

    def test_validate_license_null_in_array(self):
        """Null item in licenses array should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {
                "licenses": [None],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("licenses[0]" in e and "cannot be null" in e for e in errors))

    def test_validate_non_standard_license_enum_produces_warning(self):
        """Non-standard license name should produce warning, not error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "Production",
            "permissions": {
                "licenses": [{"name": "CustomLicense", "URL": "https://example.com/license"}],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertTrue(any("CustomLicense" in w for w in warnings))

    def test_validate_non_standard_status_enum_produces_warning(self):
        """Non-standard status should produce warning, not error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": "CustomStatus",
            "permissions": {
                "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertTrue(any("CustomStatus" in w for w in warnings))

    def test_validate_status_wrong_type(self):
        """Status as non-string should produce error."""
        record = {
            "name": "Test",
            "identifier": "test",
            "organization": "org",
            "status": 123,
            "permissions": {
                "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}],
                "usageType": []
            },
            "reuseFrequency": {},
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "contractNumber": [],
            "contact": {},
            "feedbackMechanism": "https://example.com/feedback"
        }
        is_valid, errors, warnings = validate_record(record)
        self.assertTrue(is_valid)
        self.assertTrue(any("status" in e and "must be string" in e for e in errors))


if __name__ == "__main__":
    unittest.main()


class FillRecordTests(unittest.TestCase):
    """Tests for fill_record function."""

    def test_fill_adds_missing_permissions(self):
        """Missing permissions should be added with empty arrays."""
        record = {
            "name": "Test",
            "organization": "Org"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIn("permissions", filled)
        self.assertEqual(filled["permissions"]["licenses"], [])
        self.assertEqual(filled["permissions"]["usageType"], [])
        self.assertIn("permissions", derived)

    def test_fill_removes_null_items_in_licenses(self):
        """Null items in licenses array should be removed."""
        record = {
            "name": "Test",
            "permissions": {
                "licenses": [None, {"name": "MIT", "URL": "https://example.com"}, None],
                "usageType": []
            }
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(len(filled["permissions"]["licenses"]), 1)
        self.assertEqual(filled["permissions"]["licenses"][0]["name"], "MIT")

    def test_fill_standardizes_license_names(self):
        """License names should be standardized if possible."""
        record = {
            "name": "Test",
            "permissions": {
                "licenses": [{"name": "mit license", "URL": "https://example.com"}],
                "usageType": []
            }
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["permissions"]["licenses"][0]["name"], "MIT")
        self.assertIn("MIT", derived["permissions.licenses[0].name"])

    def test_fill_keeps_non_standardizable_license(self):
        """Non-standardizable license should be kept as-is."""
        record = {
            "name": "Test",
            "permissions": {
                "licenses": [{"name": "CustomLicense", "URL": "https://example.com"}],
                "usageType": []
            }
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["permissions"]["licenses"][0]["name"], "CustomLicense")
        self.assertIn("not mappable", derived["permissions.licenses[0].name"])

    def test_fill_repositoryURL_private_for_closed_code(self):
        """Closed code with no URL should get 'private' as repositoryURL."""
        record = {
            "name": "Test",
            "permissions": {
                "licenses": [],
                "usageType": ["exemptByNationalSecurity"]
            }
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["repositoryURL"], "private")
        self.assertIn("private", derived["repositoryURL"])

    def test_fill_repositoryURL_none_for_open_code_no_url(self):
        """Open code with no URL should get None as repositoryURL."""
        record = {
            "name": "Test",
            "permissions": {
                "licenses": [],
                "usageType": ["openSource"]
            }
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIsNone(filled["repositoryURL"])
        self.assertIn("not provided", derived["repositoryURL"])

    def test_fill_repositoryVisibility_inferred_from_private_url(self):
        """RepositoryVisibility should be 'private' if URL is 'private'."""
        record = {
            "name": "Test",
            "repositoryURL": "private"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["repositoryVisibility"], "private")
        self.assertIn("inferred", derived["repositoryVisibility"])

    def test_fill_visibility_is_not_inferred_from_http_urls(self):
        for url in ("https://github.com/owner/repo", "http://example.org/repo",
                    "https://example.org/repo"):
            for visibility in ({}, {"repositoryVisibility": None}):
                with self.subTest(url=url, visibility=visibility):
                    record = {"name": "Test", "repositoryURL": url, **visibility}
                    filled, derived = fill_record("TEST_AGENCY", "file.json", record)
                    self.assertIsNone(filled["repositoryVisibility"])
                    self.assertEqual(derived["repositoryVisibility"],
                                     "not provided; repository URL does not establish visibility")
                    if "github.com" in url:
                        self.assertEqual(filled["feedbackMechanism"], url + "/issues")
                        self.assertEqual(filled["vcs"], "git")

    def test_fill_preserves_explicit_repository_visibility(self):
        for visibility in ("public", "private"):
            with self.subTest(visibility=visibility):
                record = {"repositoryURL": "https://github.com/owner/repo",
                          "repositoryVisibility": visibility}
                filled, derived = fill_record("TEST_AGENCY", "file.json", record)
                self.assertEqual(filled["repositoryVisibility"], visibility)
                self.assertNotIn("repositoryVisibility", derived)

    def test_missing_identifier_is_null_even_with_url_or_name(self):
        for record in ({}, {"name": "My Project"},
                       {"repositoryURL": "https://github.com/o/repo"}):
            filled, derived = fill_record("TEST", "file.json", record)
            self.assertIsNone(filled["identifier"])
            self.assertEqual(derived["identifier"], "not supplied by agency")

    def test_agency_identifier_is_preserved(self):
        filled, derived = fill_record("TEST", "file.json", {"identifier": "000123"})
        self.assertEqual(filled["identifier"], "000123")
        self.assertNotIn("identifier", derived)

    def test_fill_organization_inferred_from_agency(self):
        """Organization should be inferred from agency folder name."""
        record = {"name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["organization"], "TEST_AGENCY")
        self.assertIn("inferred", derived["organization"])

    def test_fill_status_standardized(self):
        """Status should be standardized if mappable."""
        record = {
            "name": "Test",
            "status": "alpha"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["status"], "Alpha")
        self.assertIn("standardized", derived["status"])

    def test_fill_status_kept_if_not_standardizable(self):
        """Status should be kept if not mappable."""
        record = {
            "name": "Test",
            "status": "CustomStatus"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["status"], "CustomStatus")
        self.assertIn("not mappable", derived["status"])

    def test_fill_maintenance_not_guessed(self):
        """Missing maintenance should not be guessed."""
        record = {"name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIsNone(filled["maintenance"])
        self.assertIn("not filled", derived["maintenance"])

    def test_fill_vcs_inferred_from_github(self):
        """VCS should be inferred as 'git' from GitHub URL."""
        record = {
            "name": "Test",
            "repositoryURL": "https://github.com/owner/repo"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["vcs"], "git")
        self.assertIn("github", derived["vcs"])

    def test_fill_vcs_none_if_not_github(self):
        """VCS should be None if not a GitHub repo."""
        record = {
            "name": "Test",
            "repositoryURL": "https://gitlab.com/owner/repo"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIsNone(filled["vcs"])
        self.assertIn("not provided", derived["vcs"])

    def test_fill_feedbackMechanism_inferred_from_github(self):
        """FeedbackMechanism should be inferred from GitHub issues URL."""
        record = {
            "name": "Test",
            "repositoryURL": "https://github.com/owner/repo"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIn("issues", filled["feedbackMechanism"])
        self.assertIn("owner/repo", filled["feedbackMechanism"])
        self.assertIn("github", derived["feedbackMechanism"])

    def test_fill_feedbackMechanism_none_if_not_github(self):
        """FeedbackMechanism should be None if not a GitHub repo."""
        record = {
            "name": "Test",
            "repositoryURL": "https://gitlab.com/owner/repo"
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertIsNone(filled["feedbackMechanism"])

    def test_fill_adds_empty_reuseFrequency(self):
        """Missing reuseFrequency should be added as empty object."""
        record = {"name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["reuseFrequency"], {})
        self.assertIn("reuseFrequency", derived)

    def test_fill_adds_empty_contractNumber(self):
        """Missing contractNumber should be added as empty array."""
        record = {"name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["contractNumber"], [])
        self.assertIn("contractNumber", derived)

    def test_fill_adds_empty_contact(self):
        """Missing contact should be added as empty object."""
        record = {"name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["contact"], {})
        self.assertIn("contact", derived)

    def test_fill_preserves_non_required_fields(self):
        """Non-required fields should be preserved."""
        record = {
            "name": "Test",
            "customField": "customValue",
            "nested": {"key": "value"}
        }
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        self.assertEqual(filled["customField"], "customValue")
        self.assertEqual(filled["nested"], {"key": "value"})

    def test_fill_orders_required_fields_first(self):
        """Required fields should come first in returned dict."""
        record = {"z_custom": "value", "name": "Test"}
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        keys = list(filled.keys())
        # First 13 keys should be required fields
        required_positions = [i for i, k in enumerate(keys) if k in [
            "name", "identifier", "organization", "status",
            "permissions", "reuseFrequency", "repositoryURL",
            "repositoryVisibility", "maintenance", "contractNumber",
            "contact", "feedbackMechanism"
        ]]
        self.assertEqual(required_positions, list(range(len(required_positions))))


class IdentityTests(unittest.TestCase):
    """Tests for has_identity function."""

    def test_has_identity_with_name(self):
        """Record with name has identity."""
        record = {"name": "Test Project"}
        self.assertTrue(has_identity(record))

    def test_has_identity_without_name(self):
        """Record without name should check URL."""
        record = {"name": None}
        self.assertFalse(has_identity(record))

    def test_has_identity_with_public_url(self):
        """Record with public URL has identity."""
        record = {"name": None, "repositoryURL": "https://github.com/owner/repo"}
        self.assertTrue(has_identity(record))

    def test_has_identity_with_private_url(self):
        """Record with 'private' URL does not have identity."""
        record = {"name": None, "repositoryURL": "private"}
        self.assertFalse(has_identity(record))

    def test_has_identity_empty_record(self):
        """Empty record does not have identity."""
        record = {}
        self.assertFalse(has_identity(record))


if __name__ == "__main__":
    unittest.main()


# ============================================================================
# COMPREHENSIVE TEST FIXTURES - Based on Real Agency Data
# ============================================================================

class RealWorldDataFixtures(unittest.TestCase):
    """Test fixtures based on real data from agency-indexes directories.
    
    These fixtures represent actual JSON structures from federal agencies,
    including legacy formats, messy data, and various edge cases.
    """

    # === Fixture 1: VA Legacy Format (like actual VA projects) ===
    VA_LEGACY_PROJECT = {
        "identifier": "va-national-clozapine-registry",  # Added required field
        "id": 2294,  # Legacy: should be converted to string identifier
        "name": "National Clozapine Registry",
        "organization": "OIT DSO",
        "version": "7.2.0",
        "status": "Development",
        "permissions": {
            "usageType": "governmentWideReuse",  # Legacy: string instead of array
            "licenses": [
                {
                    "name": "",  # Empty license name
                    "opRL": ""
                }
            ]
        },
        "repositoryURL": "https://github.com/department-of-veterans-affairs/NCC-v7.2.0",
        "repositoryVisibility": "public",  # Added required field
        "maintenance": "internal",  # Added required field
        "feedbackMechanism": "https://github.com/department-of-veterans-affairs/NCC-v7.2.0/issues",  # Added required field
        "contractNumber": [],  # Added required field
        "reuseFrequency": {},  # Added required field
        "homepageURL": "https://github.com/department-of-veterans-affairs",
        "downloadURL": "https://github.com/department-of-veterans-affairs",
        "disclaimerText": "License information not currently available.",
        "vcs": "git",
        "laborHours": 1,
        "tags": ["NCR", "Development", "governmentWideReuse"],
        "languages": ["Microsoft SQL Server", "Microsoft .NET Core"],
        "contact": {
            "name": "DSO Code Sharing Services",
            "email": "OSSOFT@va.gov",
            "URL": "https://www.va.gov",
            "phone": "844-698-2311"
        },
        "date": {
            "created": "2020-04-28",
            "lastModified": "2020-08-20",
            "metadataLastUpdated": "2020-08-20"
        },
        "description": "Repository containing the CIF submission for National Clozapine Coordination"
    }

    # === Fixture 2: Minimal Project (bare minimum required fields) ===
    MINIMAL_PROJECT = {
        "identifier": "agency-simple-project",
        "name": "Simple Project",
        "organization": "Test Agency",
        "status": "Production",
        "permissions": {
            "usageType": ["openSource"],
            "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}]
        },
        "repositoryURL": "https://github.com/agency/project",
        "repositoryVisibility": "public",
        "maintenance": "internal",
        "feedbackMechanism": "https://github.com/agency/project/issues",
        "contractNumber": [],
        "contact": {},
        "reuseFrequency": {}
    }

    # === Fixture 3: Maximal Project (all optional fields populated) ===
    MAXIMAL_PROJECT = {
        "identifier": "agency-project-123",
        "name": "Comprehensive Government Software Platform",
        "organization": "Department of Interior",
        "version": "3.2.1",
        "status": "Production",
        "description": "A comprehensive platform for managing public lands and resources.",
        "permissions": {
            "usageType": ["openSource", "governmentWideReuse"],
            "licenses": [
                {"name": "Apache-2.0", "URL": "https://opensource.org/licenses/Apache-2.0"},
                {"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}
            ]
        },
        "repositoryURL": "https://github.com/department-of-interior/lands-platform.git",
        "repositoryVisibility": "public",
        "downloadURL": "https://github.com/department-of-interior/lands-platform/releases",
        "homepageURL": "https://lands.interior.gov",
        "feedbackMechanism": "https://github.com/department-of-interior/lands-platform/issues",
        "maintenance": "contract",
        "vcs": "git",
        "laborHours": 2500,
        "tags": ["public-lands", "environment", "government", "web-app", "api"],
        "languages": ["Python", "JavaScript", "PostgreSQL", "Docker"],
        "contact": {
            "name": "Public Lands Development Team",
            "email": "dev@lands.interior.gov",
            "URL": "https://lands.interior.gov/contact",
            "phone": "+1-303-445-7111"
        },
        "date": {
            "created": "2015-06-15",
            "lastModified": "2024-11-15",
            "metadataLastUpdated": "2024-11-17"
        },
        "contractNumber": ["DOI-2024-001", "DOI-2024-002"],
        "reuseFrequency": {"frequency": "monthly"}
    }

    # === Fixture 4: Closed Code (Exempted by National Security) ===
    CLOSED_CODE_PROJECT = {
        "name": "Classified Operations Platform",
        "organization": "Department of Defense",
        "status": "Production",
        "permissions": {
            "usageType": ["exemptByNationalSecurity"],  # Closed code indicator
            "licenses": [{"name": "None", "URL": ""}]
        },
        "repositoryURL": None,  # No public repo
        "repositoryVisibility": "private",
        "maintenance": "internal",
        "feedbackMechanism": None,
        "vcs": None,
        "contractNumber": ["DOD-SECRET-001"],
        "contact": {
            "name": "Operations Security",
            "email": "opsec@defense.gov"
        },
        "reuseFrequency": {},
        "description": "Internal operational platform - not for public release."
    }

    # === Fixture 5: GitHub Enterprise Format ===
    GITHUB_ENTERPRISE_PROJECT = {
        "identifier": "commerce-analytics-dashboard",
        "name": "Enterprise Analytics Dashboard",
        "organization": "Commerce Department",
        "status": "Beta",
        "permissions": {
            "usageType": ["openSource"],
            "licenses": [{"name": "GPL-3.0-or-later", "URL": "https://www.gnu.org/licenses/gpl-3.0-en.html"}]
        },
        "repositoryURL": "https://github.com/commerce-dept/analytics-dashboard.git",
        "repositoryVisibility": "public",
        "maintenance": "community",
        "feedbackMechanism": "https://github.com/commerce-dept/analytics-dashboard/issues",
        "contractNumber": [],
        "contact": {"name": "Analytics Team", "email": "analytics@commerce.gov"},
        "reuseFrequency": {"frequency": "weekly"}
    }

    # === Fixture 6: Mixed Types and Null Values ===
    MESSY_DATA_PROJECT = {
        "identifier": 123,  # Wrong type: int instead of string
        "name": "   Project with Spaces   ",  # Whitespace issues
        "organization": None,  # Null organization
        "status": "BETA",  # Wrong case
        "version": "",  # Empty string
        "permissions": {
            "usageType": "openSource",  # String instead of array
            "licenses": [
                None,  # Null license item
                {"name": None, "URL": "https://example.com"},  # Null name
                {"name": "CustomLicense", "URL": None},  # Null URL
            ]
        },
        "repositoryURL": "HTTPS://GITHUB.COM/AGENCY/PROJECT.GIT/",  # Wrong case and format
        "repositoryVisibility": "PUBLIC",  # Wrong case
        "maintenance": "unknown-value",  # Non-standard enum
        "vcs": "git",
        "feedbackMechanism": "Contact us at email",  # Not a URL
        "contractNumber": "single-string",  # Should be array
        "contact": "not-an-object",  # Should be object
        "reuseFrequency": None,
        "description": "This project has messy, inconsistent data that needs normalization"
    }

    # === Fixture 7: Non-GitHub Repository ===
    GITLAB_PROJECT = {
        "name": "Internal Tools Suite",
        "organization": "Labor Department",
        "status": "Production",
        "permissions": {
            "usageType": ["governmentWideReuse"],
            "licenses": [{"name": "BSD-3-Clause", "URL": "https://opensource.org/licenses/BSD-3-Clause"}]
        },
        "repositoryURL": "https://gitlab.com/labor-dept/internal-tools",
        "repositoryVisibility": "private",
        "maintenance": "internal",
        "vcs": "git",  # Inferred to be git even though not GitHub
        "feedbackMechanism": None,  # Can't infer GitHub issues for non-GitHub
        "contractNumber": [],
        "contact": {"name": "Tools Team", "email": "tools@labor.gov"},
        "reuseFrequency": {}
    }

    # === Fixture 8: SVN Repository (non-git VCS) ===
    SVN_PROJECT = {
        "name": "Legacy Code Repository",
        "organization": "Transportation Department",
        "status": "Archival",
        "permissions": {
            "usageType": ["openSource"],
            "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}]
        },
        "repositoryURL": "https://svn.example.com/tdot/legacy-code",
        "repositoryVisibility": "public",
        "maintenance": "none",  # Archival, no maintenance
        "vcs": "svn",
        "feedbackMechanism": None,
        "contractNumber": [],
        "contact": {"name": "Legacy Systems", "email": "legacy@transportation.gov"},
        "reuseFrequency": {}
    }

    # === Fixture 9: Multiple Licenses (Complex Permissions) ===
    MULTI_LICENSE_PROJECT = {
        "name": "Composite Platform",
        "organization": "Health and Human Services",
        "status": "Production",
        "permissions": {
            "usageType": [
                "openSource",
                "governmentWideReuse",
                "exemptByClassifiedInformation"  # Mixed: open + exempt?
            ],
            "licenses": [
                {"name": "Apache-2.0", "URL": "https://opensource.org/licenses/Apache-2.0"},
                {"name": "MIT", "URL": "https://opensource.org/licenses/MIT"},
                {"name": "GPL-2.0-only", "URL": "https://opensource.org/licenses/GPL-2.0"},
                {"name": "Custom Internal License", "URL": "https://hhs.gov/licenses/custom"},
                {"name": "Other", "URL": ""}
            ]
        },
        "repositoryURL": "https://github.com/hhs/composite-platform",
        "repositoryVisibility": "public",
        "maintenance": "contract",
        "vcs": "git",
        "feedbackMechanism": "https://github.com/hhs/composite-platform/issues",
        "contractNumber": ["HHS-2024-CONTRACT-001"],
        "contact": {"name": "Platform Team", "email": "platform@hhs.gov"},
        "reuseFrequency": {"frequency": "daily"}
    }

    # === Fixture 10: Special Characters and Unicode ===
    SPECIAL_CHARS_PROJECT = {
        "name": "Platform für öffentliche Verwaltung (Public Admin Platform)",
        "organization": "Special Characters & Unicöde Agency",
        "status": "Production",
        "permissions": {
            "usageType": ["openSource"],
            "licenses": [{"name": "MIT", "URL": "https://opensource.org/licenses/MIT"}]
        },
        "repositoryURL": "https://github.com/special-agency/plattform-offentliche",
        "repositoryVisibility": "public",
        "maintenance": "internal",
        "vcs": "git",
        "feedbackMechanism": "https://github.com/special-agency/plattform-offentliche/issues",
        "description": "Platform with émojis 🚀 and spëcial çharacters",
        "tags": ["platföärm", "администрация", "平台"],
        "languages": ["Pythön", "JavaScrípt"],
        "contractNumber": [],
        "contact": {"name": "Special Team", "email": "special@agency.gov"},
        "reuseFrequency": {}
    }

    # === Fixture 11: Private Repository (commercial software) ===
    PRIVATE_REPO_PROJECT = {
        "name": "Commercial Integration Platform",
        "organization": "Commerce Department",
        "status": "Production",
        "permissions": {
            "usageType": ["exemptByCommercialSoftware"],
            "licenses": [{"name": "None", "URL": ""}]
        },
        "repositoryURL": "private",  # Special "private" value
        "repositoryVisibility": "private",
        "maintenance": "contract",
        "vcs": None,
        "feedbackMechanism": None,
        "contractNumber": ["COMM-VENDOR-2024"],
        "contact": {"name": "Vendor Liaison", "email": "vendor@commerce.gov"},
        "reuseFrequency": {}
    }

    # === Fixture 12: Date Variations ===
    DATE_VARIATIONS_PROJECT = {
        "name": "Project with Various Date Formats",
        "organization": "Energy Department",
        "status": "Production",
        "permissions": {
            "usageType": ["openSource"],
            "licenses": [{"name": "Apache-2.0", "URL": "https://opensource.org/licenses/Apache-2.0"}]
        },
        "repositoryURL": "https://github.com/energy-dept/project",
        "repositoryVisibility": "public",
        "maintenance": "internal",
        "vcs": "git",
        "feedbackMechanism": "https://github.com/energy-dept/project/issues",
        "date": {
            "created": "2010-01-15",  # Very old
            "lastModified": "2024-11-17",  # Very recent
            "metadataLastUpdated": "2024-11-17"
        },
        "contractNumber": [],
        "contact": {"name": "Energy Team", "email": "dev@energy.gov"},
        "reuseFrequency": {"frequency": "yearly"}
    }


class RealisticDataValidationTests(unittest.TestCase):
    """Test validate_record and fill_record with realistic data fixtures."""

    def test_validate_va_legacy_format(self):
        """VA legacy format should validate (empty license names are soft warning)."""
        record = RealWorldDataFixtures.VA_LEGACY_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        # Should validate despite legacy format
        self.assertTrue(is_valid)
        # May have warnings about legacy format, but should not error
        self.assertLess(len(errors), 5)

    def test_validate_minimal_project(self):
        """Minimal project with required fields only should validate."""
        record = RealWorldDataFixtures.MINIMAL_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_maximal_project(self):
        """Maximal project with all fields should validate."""
        record = RealWorldDataFixtures.MAXIMAL_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_closed_code_project(self):
        """Closed code project should validate."""
        record = RealWorldDataFixtures.CLOSED_CODE_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)
        # May have warnings about None values, but should validate

    def test_validate_github_enterprise(self):
        """GitHub enterprise project should validate."""
        record = RealWorldDataFixtures.GITHUB_ENTERPRISE_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_gitlab_project(self):
        """GitLab project should validate (even though not GitHub)."""
        record = RealWorldDataFixtures.GITLAB_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_svn_project(self):
        """SVN project (non-git) should validate."""
        record = RealWorldDataFixtures.SVN_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_multi_license_project(self):
        """Project with multiple licenses should validate."""
        record = RealWorldDataFixtures.MULTI_LICENSE_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_private_repo_project(self):
        """Private repository project should validate."""
        record = RealWorldDataFixtures.PRIVATE_REPO_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_special_chars_project(self):
        """Project with special characters and unicode should validate."""
        record = RealWorldDataFixtures.SPECIAL_CHARS_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_validate_date_variations_project(self):
        """Project with various date formats should validate."""
        record = RealWorldDataFixtures.DATE_VARIATIONS_PROJECT
        is_valid, errors, warnings = validate_record(record)
        
        self.assertTrue(is_valid)

    def test_fill_va_legacy_format(self):
        """VA legacy format should fill and infer missing fields."""
        record = RealWorldDataFixtures.VA_LEGACY_PROJECT.copy()
        filled, derived = fill_record("VA", "file.json", record)
        
        # This fixture supplies an agency identifier
        self.assertIn("identifier", filled)
        self.assertIsNotNone(filled["identifier"])
        
        # Should derive organization from agency if missing
        self.assertIn("organization", filled)

    def test_fill_minimal_project(self):
        """Minimal project should get all required fields filled."""
        record = RealWorldDataFixtures.MINIMAL_PROJECT.copy()
        filled, derived = fill_record("TEST_AGENCY", "file.json", record)
        
        # All required fields should exist
        for field in ["name", "identifier", "organization", "status",
                     "permissions", "reuseFrequency", "repositoryURL",
                     "repositoryVisibility", "maintenance", "contractNumber",
                     "contact", "feedbackMechanism"]:
            self.assertIn(field, filled)

    def test_fill_github_project_infers_vcs(self):
        """GitHub project should have VCS inferred as git."""
        record = RealWorldDataFixtures.GITHUB_ENTERPRISE_PROJECT.copy()
        filled, derived = fill_record("COMMERCE", "file.json", record)
        
        self.assertEqual(filled["vcs"], "git")
        self.assertIn("github", derived.get("vcs", "").lower())

    def test_fill_github_project_infers_feedback_url(self):
        """GitHub project should have feedback mechanism as GitHub issues."""
        record = RealWorldDataFixtures.GITHUB_ENTERPRISE_PROJECT.copy()
        filled, derived = fill_record("COMMERCE", "file.json", record)
        
        self.assertIn("issues", filled["feedbackMechanism"])
        self.assertIn("github.com", filled["feedbackMechanism"])

    def test_fill_closed_code_sets_private_url(self):
        """Closed code with no repository should get 'private' as URL."""
        record = RealWorldDataFixtures.CLOSED_CODE_PROJECT.copy()
        filled, derived = fill_record("DOD", "file.json", record)
        
        self.assertEqual(filled["repositoryURL"], "private")

    def test_fill_gitlab_does_not_infer_github_feedback(self):
        """GitLab project should not infer GitHub issues URL."""
        record = RealWorldDataFixtures.GITLAB_PROJECT.copy()
        filled, derived = fill_record("LABOR", "file.json", record)
        
        # GitLab shouldn't get GitHub issues URL
        if filled["feedbackMechanism"] is not None:
            self.assertNotIn("github.com", filled["feedbackMechanism"])

    def test_fill_private_repo_visibility(self):
        """Private repo indicator should infer private visibility."""
        record = RealWorldDataFixtures.PRIVATE_REPO_PROJECT.copy()
        filled, derived = fill_record("COMMERCE", "file.json", record)
        
        self.assertEqual(filled["repositoryVisibility"], "private")

    def test_fill_missing_identifier_stays_null(self):
        """Repository URLs must not invent agency identifiers."""
        record = RealWorldDataFixtures.GITHUB_ENTERPRISE_PROJECT.copy()
        # Remove the agency-reported identifier
        del record["identifier"]
        filled, derived = fill_record("COMMERCE", "file.json", record)
        
        # Missing agency values remain null
        self.assertIsNone(filled["identifier"])

    def test_identity_github_project(self):
        """GitHub project has identity (name or URL)."""
        record = RealWorldDataFixtures.GITHUB_ENTERPRISE_PROJECT
        self.assertTrue(has_identity(record))

    def test_identity_closed_code(self):
        """Closed code with no public URL needs at least a name."""
        record = RealWorldDataFixtures.CLOSED_CODE_PROJECT
        self.assertTrue(has_identity(record))  # Has name

    def test_identity_private_repo(self):
        """Private repo indicated by 'private' string needs name."""
        record = RealWorldDataFixtures.PRIVATE_REPO_PROJECT
        # Has name, so has identity
        self.assertTrue(has_identity(record))


if __name__ == "__main__":
    unittest.main()
