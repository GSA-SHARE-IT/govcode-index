#!/usr/bin/env python3
"""Convert gov-code.json to flattened CSV format.

This script reads the hierarchical gov-code.json file and converts it to a flat CSV
with the following transformations:
- Adds 'agency' field from parent object to each project
- Flattens nested objects (contact, date, permissions, reuseFrequency)
- Concatenates arrays with pipe separator (|)
- Handles null/empty values gracefully
- Outputs to gov-code-flattened.csv

Flattening strategy:
- contact.* → contact_email, contact_name, contact_url, contact_phone
- date.* → date_created, date_lastModified, date_metadataLastUpdated
- reuseFrequency.* → reuseFrequency_forks, reuseFrequency_clones, reuseFrequency_downloads
- permissions.licenses[] → permissions_licenses (pipe-separated names)
- permissions.usageType[] → permissions_usageType (pipe-separated values)
- relatedCode[], reusedCode[], languages[], tags[], contractNumber[] → pipe-separated
"""

import csv
import json
import sys
from pathlib import Path


def normalize_string(s):
    """Normalize a string by removing newlines and extra whitespace.
    
    Args:
        s: String to normalize
        
    Returns:
        Normalized string with newlines replaced by spaces
    """
    if not s:
        return ""
    # Replace newlines and tabs with spaces, strip, and collapse multiple spaces
    s = str(s).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # Collapse multiple spaces into single space
    while '  ' in s:
        s = s.replace('  ', ' ')
    return s.strip()


def flatten_array_to_string(arr, delimiter="|"):
    """Convert array to pipe-separated string.
    
    Args:
        arr: List or None
        delimiter: Character to use for joining (default: |)
        
    Returns:
        Pipe-separated string or empty string if array is empty/None
    """
    if not arr or not isinstance(arr, list):
        return ""
    
    # Convert all items to strings and normalize
    items = [normalize_string(item) for item in arr if item is not None and item != ""]
    return delimiter.join(items)


def flatten_license_array(licenses, delimiter="|"):
    """Extract license names from license array.
    
    Args:
        licenses: List of license dicts with 'name' and 'URL' keys
        delimiter: Character to use for joining (default: |)
        
    Returns:
        Pipe-separated license names or empty string
    """
    if not licenses or not isinstance(licenses, list):
        return ""
    
    names = []
    for license_item in licenses:
        if isinstance(license_item, dict) and "name" in license_item:
            name = normalize_string(license_item["name"])
            if name:
                names.append(name)
    
    return delimiter.join(names)


def flatten_code_reference_array(items, delimiter="|"):
    """Flatten relatedCode/reusedCode array to pipe-separated name|URL pairs.
    
    Args:
        items: List of dicts with 'name' and 'URL' keys
        delimiter: Character to use for joining (default: |)
        
    Returns:
        Pipe-separated "name|url|name|url..." string or empty string
    """
    if not items or not isinstance(items, list):
        return ""
    
    pairs = []
    for item in items:
        if isinstance(item, dict):
            name = normalize_string(item.get("name", ""))
            url = normalize_string(item.get("URL", ""))
            if name or url:
                pairs.append(name if name else "")
                pairs.append(url if url else "")
    
    return delimiter.join(pairs) if pairs else ""


def flatten_project(project, agency):
    """Flatten a single project record.
    
    Args:
        project: Project dict from releases array
        agency: Agency name string
        
    Returns:
        Flattened dict with all fields expanded
    """
    flat = {}
    
    # Add agency (new field)
    flat["agency"] = agency
    
    # Top-level string fields
    for field in ["name", "identifier", "organization", "status", 
                  "repositoryURL", "repositoryVisibility", "feedbackMechanism",
                  "description", "downloadURL", "homepageURL", "vcs"]:
        value = project.get(field)
        flat[field] = normalize_string(value) if value else ""
    
    # Numeric field
    flat["laborHours"] = project.get("laborHours") or ""
    
    # permissions - nested dict
    permissions = project.get("permissions") or {}
    flat["permissions_licenses"] = flatten_license_array(
        permissions.get("licenses"), delimiter="|"
    )
    flat["permissions_usageType"] = flatten_array_to_string(
        permissions.get("usageType"), delimiter="|"
    )
    
    # contact - nested dict
    contact = project.get("contact") or {}
    flat["contact_email"] = normalize_string(contact.get("email")) if contact.get("email") else ""
    flat["contact_name"] = normalize_string(contact.get("name")) if contact.get("name") else ""
    flat["contact_url"] = normalize_string(contact.get("URL")) if contact.get("URL") else ""
    flat["contact_phone"] = normalize_string(contact.get("phone")) if contact.get("phone") else ""
    
    # date - nested dict
    date_obj = project.get("date") or {}
    flat["date_created"] = normalize_string(date_obj.get("created")) if date_obj.get("created") else ""
    flat["date_lastModified"] = normalize_string(date_obj.get("lastModified")) if date_obj.get("lastModified") else ""
    flat["date_metadataLastUpdated"] = normalize_string(date_obj.get("metadataLastUpdated")) if date_obj.get("metadataLastUpdated") else ""
    
    # reuseFrequency - nested dict
    reuse_freq = project.get("reuseFrequency") or {}
    flat["reuseFrequency_forks"] = reuse_freq.get("forks") or ""
    flat["reuseFrequency_clones"] = reuse_freq.get("clones") or ""
    flat["reuseFrequency_downloads"] = reuse_freq.get("downloads") or ""
    
    # Arrays - simple string arrays
    flat["languages"] = flatten_array_to_string(
        project.get("languages"), delimiter="|"
    )
    flat["tags"] = flatten_array_to_string(
        project.get("tags"), delimiter="|"
    )
    flat["contractNumber"] = flatten_array_to_string(
        project.get("contractNumber"), delimiter="|"
    )
    
    # Code references - nested object arrays
    flat["relatedCode"] = flatten_code_reference_array(
        project.get("relatedCode"), delimiter="|"
    )
    flat["reusedCode"] = flatten_code_reference_array(
        project.get("reusedCode"), delimiter="|"
    )
    
    return flat


def convert_to_csv(input_file, output_file):
    """Convert gov-code.json to flattened CSV.
    
    Args:
        input_file: Path to gov-code.json
        output_file: Path to output CSV file
    """
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    # Verify input file exists
    if not input_path.exists():
        print(f"Error: {input_file} not found", file=sys.stderr)
        return False
    
    print(f"Reading {input_file}...")
    
    # Load JSON
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return False
    
    if not isinstance(data, list):
        print(f"Error: Expected list at top level, got {type(data).__name__}", 
              file=sys.stderr)
        return False
    
    # Flatten all projects
    print("Flattening projects...")
    flattened_projects = []
    total_projects = 0
    
    for agency_obj in data:
        agency_name = agency_obj.get("agency", "UNKNOWN")
        releases = agency_obj.get("releases") or []
        
        for release in releases:
            flattened = flatten_project(release, agency_name)
            flattened_projects.append(flattened)
            total_projects += 1
    
    print(f"  Flattened {total_projects} projects from {len(data)} agencies")
    
    # Determine column order (consistent across all rows)
    # Order: agency first, then core fields, then nested, then arrays
    column_order = [
        "agency",
        # Core fields
        "name", "identifier", "organization", "status",
        # URLs
        "repositoryURL", "repositoryVisibility", "feedbackMechanism",
        "downloadURL", "homepageURL",
        # VCS and other
        "vcs", "laborHours", "description",
        # Permissions
        "permissions_licenses", "permissions_usageType",
        # Contact
        "contact_email", "contact_name", "contact_url", "contact_phone",
        # Date
        "date_created", "date_lastModified", "date_metadataLastUpdated",
        # Reuse frequency
        "reuseFrequency_forks", "reuseFrequency_clones", "reuseFrequency_downloads",
        # Code references
        "relatedCode", "reusedCode",
        # Arrays
        "languages", "tags", "contractNumber"
    ]
    
    # Write CSV
    print(f"Writing {output_file}...")
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=column_order, restval="")
            writer.writeheader()
            writer.writerows(flattened_projects)
        
        print(f"✓ Successfully wrote {total_projects} rows to {output_file}")
        
        # Print file size
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Output file size: {file_size_mb:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"Error writing CSV: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    # Default paths
    repo_root = Path(__file__).parent.parent  # scripts/ -> repository root
    input_file = repo_root / "gov-code.json"
    output_file = repo_root / "gov-code.csv"
    
    # Allow command-line override
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    success = convert_to_csv(str(input_file), str(output_file))
    sys.exit(0 if success else 1)
