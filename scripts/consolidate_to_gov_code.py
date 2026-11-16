#!/usr/bin/env python3
"""
Consolidate all agency project files into a single gov-code.json file.

This script:
1. Iterates through all agency-indexes/{AGENCY}/ directories
2. Reads all JSON files from each agency directory
3. Creates a schema-compliant agency index object per agency
4. Combines all agency indexes into a single gov-code.json array

The output file abides by the agency-index schema specification.

Schema configuration is automatically fetched from:
https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json
"""

import json
import logging
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Schema URL - will be fetched dynamically
SCHEMA_URL = "https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json"

# These will be populated from the schema
SCHEMA_VERSION = None
VALID_AGENCIES = None

def fetch_schema(url: str) -> dict | None:
    """
    Fetch the JSON schema from the remote URL.
    
    Args:
        url: URL to the schema
        
    Returns:
        Parsed schema dictionary, or None if fetch fails
    """
    try:
        logger.info(f"Fetching schema from {url}")
        with urllib.request.urlopen(url, timeout=10) as response:
            schema = json.loads(response.read().decode('utf-8'))
        logger.info("Schema fetched successfully")
        return schema
    except urllib.error.URLError as e:
        logger.error(f"Failed to fetch schema from {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching schema: {e}")
        return None

def extract_schema_config(schema: dict) -> tuple[str, set] | None:
    """
    Extract version and valid agencies from the schema.
    
    Args:
        schema: Parsed schema dictionary
        
    Returns:
        Tuple of (version, valid_agencies_set), or None if extraction fails
    """
    try:
        # Extract version
        version = schema.get('properties', {}).get('version', {}).get('type')
        if not version:
            version = "1.0.0"
        
        # Extract from the version description if available
        version_desc = schema.get('properties', {}).get('version', {}).get('description', '')
        # Try to parse version from description like "version of the metadata schema in use..."
        if 'version' in version_desc.lower():
            # Fallback to default if explicit version not found
            version = "1.0.0"
        
        # Extract agency enum values
        agency_enum = schema.get('properties', {}).get('agency', {}).get('enum', [])
        
        if not agency_enum:
            logger.warning("Could not extract agency enum from schema")
            return None
        
        valid_agencies = set(agency_enum)
        logger.info(f"Schema version: {version}")
        logger.info(f"Valid agencies found: {len(valid_agencies)}")
        
        return version, valid_agencies
    except Exception as e:
        logger.error(f"Error extracting schema configuration: {e}")
        return None


def initialize_schema_config() -> bool:
    """
    Fetch and initialize schema configuration globally.
    
    Returns:
        True if successful, False otherwise
    """
    global SCHEMA_VERSION, VALID_AGENCIES
    
    schema = fetch_schema(SCHEMA_URL)
    if not schema:
        logger.error("Failed to fetch schema. Please check your internet connection.")
        return False
    
    result = extract_schema_config(schema)
    if not result:
        logger.error("Failed to extract configuration from schema")
        return False
    
    SCHEMA_VERSION, VALID_AGENCIES = result
    return True


def load_project_file(file_path: Path) -> dict | None:
    """Load and parse a project JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def create_agency_index(agency: str, releases: list) -> dict:
    """Create a schema-compliant agency index object."""
    return {
        "version": SCHEMA_VERSION,
        "agency": agency,
        "releases": releases
    }


def consolidate_indexes(repo_root: Path) -> list:
    """
    Consolidate all agency project files into agency index objects.
    
    Returns:
        List of agency index objects
    """
    agency_indexes_dir = repo_root / "agency-indexes"
    
    if not agency_indexes_dir.exists():
        logger.error(f"Directory not found: {agency_indexes_dir}")
        return []
    
    all_agency_indexes = []
    
    # Iterate through agency subdirectories
    agency_dirs = sorted([d for d in agency_indexes_dir.iterdir() if d.is_dir()])
    
    for agency_dir in agency_dirs:
        # Directory names already follow schema (DHS, DOD, DOE, etc.)
        agency_name = agency_dir.name.upper()
        
        if agency_name not in VALID_AGENCIES:
            logger.warning(f"Skipping invalid agency directory: {agency_dir.name}")
            continue
        
        # Find all JSON files in the agency directory
        json_files = sorted(agency_dir.glob("*.json"))
        
        if not json_files:
            logger.info(f"No project files found in {agency_dir.name}")
            continue
        
        releases = []
        file_count = 0
        
        for json_file in json_files:
            # Skip index files themselves
            if json_file.name.endswith("-index.json"):
                continue
            
            project = load_project_file(json_file)
            if project:
                releases.append(project)
                file_count += 1
        
        if releases:
            agency_index = create_agency_index(agency_name, releases)
            all_agency_indexes.append(agency_index)
            logger.info(f"{agency_name}: Loaded {file_count} projects")
        else:
            logger.info(f"{agency_name}: No valid project files found")
    
    return all_agency_indexes


def save_gov_code_json(repo_root: Path, agency_indexes: list) -> bool:
    """
    Save the consolidated agency indexes to gov-code.json.
    
    Returns:
        True if successful, False otherwise
    """
    output_file = repo_root / "gov-code.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(agency_indexes, f, indent=2, ensure_ascii=False)
        
        total_releases = sum(len(idx["releases"]) for idx in agency_indexes)
        logger.info(f"Successfully saved {output_file}")
        logger.info(f"Total agencies: {len(agency_indexes)}, Total projects: {total_releases}")
        return True
    except Exception as e:
        logger.error(f"Error saving {output_file}: {e}")
        return False


def main():
    """Main entry point."""
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    logger.info("Starting consolidation of agency indexes...")
    
    # Initialize schema configuration from remote source
    logger.info(f"Initializing schema configuration from {SCHEMA_URL}")
    if not initialize_schema_config():
        logger.error("Cannot proceed without schema configuration")
        return 1
    
    # Consolidate all agency indexes
    agency_indexes = consolidate_indexes(repo_root)
    
    if not agency_indexes:
        logger.error("No agency indexes were created")
        return 1
    
    # Save to gov-code.json
    if save_gov_code_json(repo_root, agency_indexes):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
