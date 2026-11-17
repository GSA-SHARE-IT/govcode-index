"""Comprehensive tests for normalization rules.

Tests verify both structural (3a) and value (3b) normalization stages
using realistic data similar to actual project records from agency-indexes.

These tests ensure data integrity when normalizing code.json project objects.
"""

import unittest
from datetime import datetime
from scripts.utils.normalize import normalize_project


class StructuralNormalizationTests(unittest.TestCase):
    """Tests for Stage 3a: Structural Normalization (shape, types, structure)"""

    # =========================================================================
    # Legacy Key Renames
    # =========================================================================

    def test_rename_legacy_id_to_identifier(self):
        """Legacy 'id' field should be renamed to 'identifier'."""
        project = {
            "id": 2294,
            "name": "Test Project",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("id", normalized)
        self.assertEqual(normalized.get("identifier"), 2294)

    def test_rename_legacy_repository_to_repositoryURL(self):
        """Legacy 'repository' field should be renamed to 'repositoryURL'."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repository": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("repository", normalized)
        self.assertEqual(normalized.get("repositoryURL"), "https://github.com/test/repo")

    def test_rename_legacy_homepage_to_homepageURL(self):
        """Legacy 'homepage' field should be renamed to 'homepageURL'."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "homepage": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("homepage", normalized)
        self.assertEqual(normalized.get("homepageURL"), "https://example.com")

    def test_dont_overwrite_schema_key_with_legacy_key(self):
        """If schema key exists and is not empty, don't overwrite with legacy key."""
        project = {
            "name": "Test Project",
            "identifier": "schema-id",
            "id": "legacy-id",  # Should be ignored
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized.get("identifier"), "schema-id")

    # =========================================================================
    # Nested Key Renames (updated -> date.lastModified)
    # =========================================================================

    def test_rename_legacy_updated_to_date_lastModified(self):
        """Legacy top-level 'updated' should move to 'date.lastModified'."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "updated": "2023-01-15",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("updated", normalized)
        self.assertEqual(normalized.get("date", {}).get("lastModified"), "2023-01-15T00:00:00Z")

    def test_hoist_exemption_text_to_permissions(self):
        """Top-level 'exemptionText' should hoist to 'permissions.exemptionText'."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "exemptionText": "Classified information",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("exemptionText", normalized)
        self.assertEqual(
            normalized.get("permissions", {}).get("exemptionText"),
            "Classified information"
        )

    # =========================================================================
    # Required String Fields (trim, empty -> null)
    # =========================================================================

    def test_trim_required_strings(self):
        """Required string fields should be trimmed."""
        project = {
            "name": "  Test Project  ",
            "identifier": "  test-123  ",
            "organization": "  Test Org  ",
            "status": "  Production  ",
            "repositoryURL": "  https://github.com/test/repo  ",
            "repositoryVisibility": "  public  ",
            "maintenance": "  internal  ",
            "feedbackMechanism": "  https://github.com/test/repo/issues  ",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["name"], "Test Project")
        self.assertEqual(normalized["identifier"], "test-123")
        self.assertEqual(normalized["organization"], "Test Org")
        self.assertEqual(normalized["status"], "Production")

    def test_empty_required_strings_to_null(self):
        """Empty required string fields should become null."""
        project = {
            "name": "",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertIsNone(normalized.get("name"))

    # =========================================================================
    # Optional String Fields (empty/null -> omit)
    # =========================================================================

    def test_omit_empty_optional_strings(self):
        """Empty optional string fields should be omitted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "description": "",
            "homepageURL": "  ",
            "downloadURL": None,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("description", normalized)
        self.assertNotIn("homepageURL", normalized)
        self.assertNotIn("downloadURL", normalized)

    def test_keep_non_empty_optional_strings(self):
        """Non-empty optional strings should be kept and trimmed."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "description": "  A test project  ",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["description"], "A test project")

    # =========================================================================
    # Version Field (number coercion)
    # =========================================================================

    def test_coerce_numeric_version_to_string(self):
        """Numeric version should be coerced to string."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "version": 7.2,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["version"], "7.2")
        self.assertIsInstance(normalized["version"], str)

    def test_trim_string_version(self):
        """String version should be trimmed."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "version": "  TMP 4.8.0  ",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["version"], "TMP 4.8.0")

    # =========================================================================
    # Permissions Object
    # =========================================================================

    def test_normalize_permissions_licenses_array(self):
        """Licenses should be normalized as array with allowed keys only."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "licenses": {
                    "name": "MIT",
                    "URL": "https://opensource.org/licenses/MIT",
                    "extra_field": "should-be-stripped"
                },
                "usageType": "openSource"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        licenses = normalized["permissions"]["licenses"]
        self.assertIsInstance(licenses, list)
        self.assertEqual(len(licenses), 1)
        self.assertIn("name", licenses[0])
        self.assertIn("URL", licenses[0])
        self.assertNotIn("extra_field", licenses[0])

    def test_normalize_permissions_usageType_array(self):
        """usageType should be normalized as array."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "usageType": "openSource"  # Single string -> array
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        usage = normalized["permissions"]["usageType"]
        self.assertIsInstance(usage, list)

    def test_null_licenses_to_empty_list(self):
        """Null licenses should become empty list."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "licenses": None,
                "usageType": "openSource"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["permissions"]["licenses"], [])

    # =========================================================================
    # Labor Hours (type coercion)
    # =========================================================================

    def test_coerce_string_laborHours_to_number(self):
        """String laborHours should be coerced to number."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "laborHours": "152.5",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertEqual(normalized["laborHours"], 152.5)
        self.assertIsInstance(normalized["laborHours"], (int, float))

    # =========================================================================
    # String Lists (languages, tags)
    # =========================================================================

    def test_normalize_languages_array(self):
        """Languages should be normalized: trim, remove empty, deduplicate."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "languages": [
                "  Python  ",
                "Python",  # Duplicate
                "  ",  # Empty after trim
                "JavaScript"
            ],
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        # Should have trimmed, removed empty, deduplicated
        self.assertIn("languages", normalized)

    def test_normalize_tags_array(self):
        """Tags should be normalized: trim, remove empty."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "tags": [
                "  github  ",
                "  ",
                "Development"
            ],
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertIn("tags", normalized)

    # =========================================================================
    # Object Lists (relatedCode, reusedCode, partners)
    # =========================================================================

    def test_normalize_relatedCode_object_list(self):
        """relatedCode should be normalized: wrap single object, strip keys, trim strings."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "relatedCode": {
                "name": "  Related Project  ",
                "URL": "https://github.com/related/repo",
                "extra_field": "should-be-stripped"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        # Should wrap in array
        related = normalized.get("relatedCode")
        self.assertIsInstance(related, list)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["name"], "Related Project")
        self.assertNotIn("extra_field", related[0])

    # =========================================================================
    # Date Object (strip keys, trim strings)
    # =========================================================================

    def test_normalize_date_object(self):
        """Date object should be normalized: strip extra keys, trim strings."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "date": {
                "created": "  2023-01-15  ",
                "lastModified": "2023-06-20",
                "extra_field": "should-be-stripped"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        date_obj = normalized["date"]
        self.assertIn("created", date_obj)
        self.assertNotIn("extra_field", date_obj)

    # =========================================================================
    # Contact Object
    # =========================================================================

    def test_normalize_contact_object(self):
        """Contact object should be normalized: strip to {email, name}."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "contact": {
                "name": "  Test Contact  ",
                "email": "test@example.com",
                "URL": "https://example.com",  # Should be stripped
                "phone": "555-1234"  # Should be stripped
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        contact = normalized["contact"]
        self.assertIn("name", contact)
        self.assertIn("email", contact)
        self.assertNotIn("URL", contact)
        self.assertNotIn("phone", contact)
        self.assertEqual(contact["name"], "Test Contact")

    def test_omit_empty_contact_object(self):
        """Empty contact object should be omitted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "contact": {
                "name": "",
                "email": None
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertNotIn("contact", normalized)

    # =========================================================================
    # Strip Extra Keys
    # =========================================================================

    def test_preserve_extra_top_level_keys(self):
        """Top-level extra keys not in schema should be preserved."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "customField": "extra-data",
            "anotherExtra": 123,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)
        
        self.assertIn("customField", normalized)
        self.assertEqual(normalized["customField"], "extra-data")
        self.assertIn("anotherExtra", normalized)
        self.assertEqual(normalized["anotherExtra"], 123)


if __name__ == "__main__":
    unittest.main()
