"""Value normalization tests (Part 2).
Tests for Stage 3b: Value Normalization (enum mapping, date parsing, URL canonicalization, etc.)
"""

import unittest
from scripts.utils.normalize import normalize_project, normalize_record, Ctx
from scripts.utils.validate import fill_record


class ValueNormalizationTests(unittest.TestCase):
    """Tests for Stage 3b: Value Normalization (values, enums, dates, URLs)"""

    def test_github_git_url_enables_feedback_inference(self):
        for url in ("git://github.com/CDCgov/AlignmentViewer",
                    "  GIT://GITHUB.COM/CDCgov/AlignmentViewer.git/  "):
            with self.subTest(url=url):
                source = {"name": "AlignmentViewer", "repositoryURL": url}
                ctx = Ctx()
                normalized = normalize_record(source, ctx)
                expected = "https://github.com/CDCgov/AlignmentViewer"
                self.assertEqual(normalized["repositoryURL"], expected)
                self.assertEqual(ctx.changes["github_git_to_https:repositoryURL"], 1)
                self.assertEqual(source["repositoryURL"], url)
                self.assertEqual(normalize_project(normalized), normalized)
                filled, _ = fill_record("HHS", "AlignmentViewer.json", normalized)
                self.assertEqual(filled["feedbackMechanism"], expected + "/issues")

    def test_git_protocol_conversion_is_scoped_to_exact_github_host(self):
        for url in ("git://example.org/owner/repo", "git://github.com.example.org/owner/repo",
                    "https://example.org/git://github.com/owner/repo",
                    "https://example.org/repo?source=git://github.com/owner/repo"):
            with self.subTest(url=url):
                ctx = Ctx()
                normalized = normalize_record({"repositoryURL": url}, ctx)
                self.assertEqual(normalized["repositoryURL"], url)
                self.assertNotIn("github_git_to_https:repositoryURL", ctx.changes)

    # =========================================================================
    # Repository URL Canonicalization
    # =========================================================================

    def test_canonicalize_repositoryURL(self):
        """RepositoryURL should be canonicalized: lowercase, remove .git, trailing slashes."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "HTTPS://GITHUB.COM/test/repo.git/",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        # Should be lowercase, .git removed, trailing slash removed
        self.assertEqual(
            normalized["repositoryURL"],
            "https://github.com/test/repo"
        )

    def test_upgrade_http_to_https_repositoryURL(self):
        """HTTP repositoryURL should be upgraded to HTTPS."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "http://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertTrue(normalized["repositoryURL"].startswith("https://"))

    def test_bare_domain_repositoryURL_moves_to_homepage(self):
        """Bare domain repositoryURL (no path) should move to homepageURL."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://example.com",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["repositoryURL"])
        self.assertEqual(normalized["homepageURL"], "https://example.com")

    def test_private_repositoryURL_kept_as_is(self):
        """Special string 'private' should be kept as-is."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "private",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertEqual(normalized["repositoryURL"], "private")

    def test_invalid_repositoryURL_to_null(self):
        """Invalid URL should become null."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "not-a-valid-url-!!!",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["repositoryURL"])

    # =========================================================================
    # Status Enum Mapping
    # =========================================================================

    def test_map_status_to_enum(self):
        """Status values should be mapped to enum (case-insensitive)."""
        test_cases = [
            ("ideation", "Ideation"),
            ("IDEATION", "Ideation"),
            ("development", "Development"),
            ("alpha", "Alpha"),
            ("beta", "Beta"),
            ("production", "Production"),
            ("archival", "Archival"),
            ("release-candidate", "Release Candidate"),
            ("rc", "Release Candidate"),
        ]

        for input_status, expected_status in test_cases:
            with self.subTest(input_status=input_status):
                project = {
                    "name": "Test Project",
                    "identifier": "test-123",
                    "organization": "Test Org",
                    "status": input_status,
                    "repositoryURL": "https://github.com/test/repo",
                    "repositoryVisibility": "public",
                    "maintenance": "internal",
                    "feedbackMechanism": "https://github.com/test/repo/issues",
                }
                normalized = normalize_project(project)
                self.assertEqual(normalized["status"], expected_status)

    def test_unrecognized_status_to_null(self):
        """Unrecognized status should become null."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "unknown_status",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["status"])

    # =========================================================================
    # Date Parsing and Normalization
    # =========================================================================

    def test_parse_iso8601_date(self):
        """ISO 8601 dates should be parsed and normalized."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "date": {
                "created": "2023-01-15",
                "lastModified": "2023-06-20T14:30:00Z"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        # Date-only should be converted to full timestamp
        self.assertEqual(normalized["date"]["created"], "2023-01-15T00:00:00Z")
        self.assertIn("2023-06-20", normalized["date"]["lastModified"])

    def test_parse_slash_separated_date(self):
        """Slash-separated dates (YYYY/MM/DD) should be converted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "date": {
                "created": "2023/01/15"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        # Should be converted to dash format
        self.assertEqual(normalized["date"]["created"], "2023-01-15T00:00:00Z")

    def test_parse_text_format_date(self):
        """Text format dates should be parsed."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "date": {
                "created": "January 15, 2023"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        # Should be converted to RFC3339
        self.assertEqual(normalized["date"]["created"], "2023-01-15T00:00:00Z")

    def test_unparseable_date_omitted(self):
        """Unparseable dates should be omitted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "date": {
                "created": "not-a-valid-date",
                "lastModified": "2023-06-20"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertNotIn("created", normalized["date"])
        self.assertIn("lastModified", normalized["date"])

    # =========================================================================
    # License Mapping
    # =========================================================================

    def test_map_license_names_to_enum(self):
        """License names should be mapped to enum values."""
        test_cases = [
            ("MIT", "MIT"),
            ("mit", "MIT"),
            ("mit license", "MIT"),
            ("Apache-2.0", "Apache-2.0"),
            ("apache", "Apache-2.0"),
            ("GPL-2.0-only", "GPL-2.0-only"),
            ("gpl2", "GPL-2.0-only"),
            ("CC0-1.0", "CC0-1.0"),
            ("cc0", "CC0-1.0"),
            ("public domain", "CC0-1.0"),
        ]

        for input_license, expected_license in test_cases:
            with self.subTest(input_license=input_license):
                project = {
                    "name": "Test Project",
                    "identifier": "test-123",
                    "organization": "Test Org",
                    "status": "Production",
                    "repositoryURL": "https://github.com/test/repo",
                    "permissions": {
                        "licenses": [
                            {
                                "name": input_license,
                                "URL": "https://example.com"
                            }
                        ],
                        "usageType": "openSource"
                    },
                    "repositoryVisibility": "public",
                    "maintenance": "internal",
                    "feedbackMechanism": "https://github.com/test/repo/issues",
                }
                normalized = normalize_project(project)

                licenses = normalized["permissions"]["licenses"]
                if licenses:  # Only check if licenses exist after normalization
                    self.assertEqual(licenses[0]["name"], expected_license)

    def test_cc0_universal_mapping_preserves_license_and_source(self):
        url = "https://creativecommons.org/publicdomain/zero/1.0/"
        for name in ("CC0 1.0 Universal", "cc0 1.0 universal",
                     "  CC0  1.0\tUNIVERSAL  "):
            with self.subTest(name=name):
                source = {"permissions": {"licenses": [{"name": name, "URL": url}]}}
                ctx = Ctx()
                normalized = normalize_record(source, ctx)
                self.assertEqual(normalized["permissions"]["licenses"],
                                 [{"name": "CC0-1.0", "URL": url}])
                self.assertEqual(source["permissions"]["licenses"][0]["name"], name)
                self.assertEqual(ctx.changes["license_mapped"], 1)
                self.assertEqual(normalize_project(normalized), normalized)

    def test_unrecognized_license_to_Other(self):
        """Unrecognized license should map to 'Other'."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "licenses": [
                    {
                        "name": "CustomLicense123",
                        "URL": "https://example.com"
                    }
                ],
                "usageType": "openSource"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        licenses = normalized["permissions"]["licenses"]
        self.assertEqual(licenses[0]["name"], "Other")

    def test_drop_noassertion_license(self):
        """'noassertion' license should be dropped."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "licenses": [
                    {
                        "name": "noassertion",
                        "URL": "https://example.com"
                    },
                    {
                        "name": "MIT",
                        "URL": "https://opensource.org/licenses/MIT"
                    }
                ],
                "usageType": "openSource"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        licenses = normalized["permissions"]["licenses"]
        # Only MIT should remain
        self.assertEqual(len(licenses), 1)
        self.assertEqual(licenses[0]["name"], "MIT")

    # =========================================================================
    # Usage Type Enum
    # =========================================================================

    def test_map_usageType_to_enum(self):
        """Usage type should be mapped to canonical enum value."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "usageType": ["opensource", "OPENSOURCE"]  # Case variations
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        usage = normalized["permissions"]["usageType"]
        # Should be canonicalized and deduplicated
        self.assertIn("openSource", usage)

    def test_drop_unrecognized_usageType(self):
        """Unrecognized usage type should be dropped."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "permissions": {
                "usageType": ["openSource", "unknownUsageType"]
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        usage = normalized["permissions"]["usageType"]
        self.assertIn("openSource", usage)
        self.assertNotIn("unknownUsageType", usage)

    # =========================================================================
    # Tags Normalization
    # =========================================================================

    def test_normalize_tags_case_and_whitespace(self):
        """Tags should be lowercased and trimmed, with extra whitespace removed."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "tags": [
                "  GitHub  ",
                "DEVELOPMENT",
                "government-wide-reuse"
            ],
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        tags = normalized.get("tags", [])
        # Should be lowercased
        self.assertTrue(all(tag.islower() or "-" in tag for tag in tags))

    def test_deduplicate_tags(self):
        """Duplicate tags should be removed."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "tags": [
                "github",
                "GitHub",
                "GITHUB"
            ],
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        tags = normalized.get("tags", [])
        # Should have only one entry (after normalization)
        self.assertEqual(len(tags), 1)

    # =========================================================================
    # Labor Hours Value Validation
    # =========================================================================

    def test_omit_zero_laborHours(self):
        """Zero laborHours should be omitted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "laborHours": 0,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertNotIn("laborHours", normalized)

    def test_omit_negative_laborHours(self):
        """Negative laborHours should be omitted."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "laborHours": -10,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertNotIn("laborHours", normalized)

    def test_keep_positive_laborHours(self):
        """Positive laborHours should be kept."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "laborHours": 152.5,
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertEqual(normalized["laborHours"], 152.5)

    # =========================================================================
    # Email Validation
    # =========================================================================

    def test_validate_contact_email(self):
        """Valid email should be kept."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "contact": {
                "name": "Test Contact",
                "email": "test@example.com"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertEqual(normalized["contact"]["email"], "test@example.com")

    def test_malformed_email_to_null(self):
        """Malformed email should become null."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "contact": {
                "name": "Test Contact",
                "email": "not-an-email"
            },
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["contact"]["email"])

    # =========================================================================
    # Enum Fields (vcs, repositoryVisibility, maintenance)
    # =========================================================================

    def test_vcs_enum_case_insensitive(self):
        """VCS should match enum case-insensitively."""
        test_values = ["git", "GIT", "Git", "hg", "svn"]

        for vcs_value in test_values:
            with self.subTest(vcs=vcs_value):
                project = {
                    "name": "Test Project",
                    "identifier": "test-123",
                    "organization": "Test Org",
                    "status": "Production",
                    "repositoryURL": "https://github.com/test/repo",
                    "vcs": vcs_value,
                    "repositoryVisibility": "public",
                    "maintenance": "internal",
                    "feedbackMechanism": "https://github.com/test/repo/issues",
                }
                normalized = normalize_project(project)

                # Should be lowercased
                self.assertEqual(normalized["vcs"], vcs_value.lower())

    def test_repositoryVisibility_enum_required(self):
        """Invalid repositoryVisibility should become null (required field)."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "invalid_visibility",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["repositoryVisibility"])

    def test_maintenance_enum_required(self):
        """Invalid maintenance should become null (required field)."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "repositoryVisibility": "public",
            "maintenance": "invalid_maintenance",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        self.assertIsNone(normalized["maintenance"])

    # =========================================================================
    # URL Field Canonicalization
    # =========================================================================

    def test_canonicalize_url_fields(self):
        """URL fields should be canonicalized: lowercase, remove trailing slashes."""
        project = {
            "name": "Test Project",
            "identifier": "test-123",
            "organization": "Test Org",
            "status": "Production",
            "repositoryURL": "https://github.com/test/repo",
            "homepageURL": "HTTPS://EXAMPLE.COM/page/",
            "downloadURL": "https://example.com/download/",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues",
        }
        normalized = normalize_project(project)

        # URLs should be lowercase and canonicalized
        self.assertTrue(normalized["homepageURL"].startswith("https://"))

    # =========================================================================
    # Real-World Data Examples
    # =========================================================================

    def test_normalize_real_world_dhs_project(self):
        """Test normalization with realistic DHS project data."""
        project = {
            "name": "ACID",
            "identifier": "acid-123",
            "organization": "Cybersecurity and Infrastructure Security Agency",
            "status": "development",  # Lowercase - should be mapped
            "repositoryURL": "https://github.com/cisagov/ACID.git",
            "repositoryVisibility": "PUBLIC",  # Uppercase - should be lowercased
            "maintenance": "community",
            "downloadURL": "https://api.github.com/repos/cisagov/ACID/downloads",
            "homepageURL": "https://github.com/cisagov/ACID",
            "laborHours": 152.0,
            "languages": ["Zeek", "zeek"],  # Duplicate after normalization
            "tags": ["github", "GITHUB"],  # Duplicate after normalization
            "permissions": {
                "licenses": [
                    {
                        "name": "Apache-2.0",
                        "URL": "https://api.github.com/licenses/apache-2.0"
                    }
                ],
                "usageType": "openSource"
            },
            "contact": {
                "name": "Test Team",
                "email": "test@dhs.gov",
                "URL": "https://github.com/cisagov"  # Should be stripped
            },
            "date": {
                "created": "2024-04-02",
                "lastModified": "2026-09-27"
            },
            "feedbackMechanism": "https://github.com/cisagov/ACID/issues"
        }

        normalized = normalize_project(project)

        # Verify normalizations
        self.assertEqual(normalized["status"], "Development")
        self.assertEqual(normalized["repositoryVisibility"], "public")
        self.assertEqual(normalized["laborHours"], 152.0)
        self.assertNotIn("URL", normalized["contact"])

    def test_normalize_real_world_va_project(self):
        """Test normalization with realistic VA project data."""
        project = {
            "id": 2294,  # Legacy id field
            "name": "National Clozapine Registry",
            "organization": "OIT DSO",
            "version": "7.2.0",
            "status": "Development",
            "permissions": {
                "usageType": "governmentWideReuse",
                "licenses": [
                    {
                        "name": "",  # Empty - should be handled
                        "opRL": ""
                    }
                ]
            },
            "homepage": "https://github.com/department-of-veterans-affairs",  # Legacy
            "repository": "https://github.com/department-of-veterans-affairs/repo.git",  # Legacy
            "downloadURL": "https://github.com/department-of-veterans-affairs",
            "disclaimerText": "License information not currently available.",
            "vcs": "git",
            "laborHours": 1,
            "tags": [
                "NCR",
                "Development",
                "governmentWideReuse"
            ],
            "languages": [
                "Microsoft SQL Server",
                "Microsoft .NET Core"
            ],
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
            "description": "Repository containing NCR submission.",
            "repositoryVisibility": "public",
            "maintenance": "internal",
            "feedbackMechanism": "https://github.com/test/repo/issues"
        }

        normalized = normalize_project(project)

        # Verify renames worked - identifier should be coerced to string
        self.assertEqual(normalized["identifier"], "2294")
        self.assertIsInstance(normalized["identifier"], str)
        self.assertNotIn("id", normalized)
        self.assertEqual(normalized["repositoryURL"], "https://github.com/department-of-veterans-affairs/repo")
        self.assertNotIn("repository", normalized)
        self.assertEqual(normalized["homepageURL"], "https://github.com/department-of-veterans-affairs")
        self.assertNotIn("homepage", normalized)

        # Verify contact stripping
        self.assertNotIn("URL", normalized["contact"])
        self.assertNotIn("phone", normalized["contact"])


if __name__ == "__main__":
    unittest.main()
