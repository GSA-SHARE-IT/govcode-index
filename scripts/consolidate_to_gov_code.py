#!/usr/bin/env python3
"""
Consolidate all agency project files into a single gov-code.json file.

This script:
1. Iterates through all agency-indexes/{AGENCY}/ directories
2. Reads all JSON files from each agency directory
3. Creates a schema-compliant agency index object per agency
4. Combines all agency indexes into a single gov-code.json array

The output file abides by the agency-index schema specification.

Schema configuration is automatically fetched from the official schema source.
"""

import json
import logging
import sys
from pathlib import Path

from utils.validate import validate_record, fill_record
from utils.schema import initialize_schema_config, validate_agency_index
from utils.normalize import normalize_project


AGENCY_INDEX_URL = "https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index/schema-1.0.0.json"
logger = logging.getLogger(__name__)

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


def normalize_project_file(project: dict, agency: str, file_path: Path) -> dict | None:
    """
    Normalize, validate, and fill a project object.
    
    Args:
        project: The project object to normalize
        agency: The agency name (for filling derivation)
        file_path: Path to the project file (for logging)
        
    Returns:
        The filled and validated project object
    """
    # Stage 3: Normalize the project structure and values
    normalized = normalize_project(project)
    
    # Stage 4: Validate (soft validation - non-blocking)
    is_valid, errors, warnings = validate_record(normalized)
    
    # Log validation results
    if errors:
        logger.warning(f"{file_path.name}: Validation errors: {', '.join(errors[:3])}")
    if warnings:
        logger.debug(f"{file_path.name}: Validation warnings: {len(warnings)} found")
    
    # Stage 5: Fill required fields and standardize
    filled, derivation = fill_record(agency, file_path.name, normalized)
    
    return filled


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
            # Only reserved agency snapshot names are indexes; project names
            # can legitimately end in "-index.json".
            if json_file.name.casefold() in {
                f"{agency_name.lower()}-index.json",
                f"{agency_name.lower()}-public-index.json",
            }:
                continue
            
            project = load_project_file(json_file)
            if project:
                project = normalize_project_file(project, agency_name, json_file)
                if project:
                    releases.append(project)
                    file_count += 1
        
        if releases:
            agency_index = create_agency_index(agency_name, releases)
            
            # Validate agency index immediately after creation
            is_valid, errors = validate_agency_index(agency_index, SCHEMA_VERSION, VALID_AGENCIES)
            if not is_valid:
                logger.error(f"{agency_name}: Schema validation failed")
                for error in errors:
                    logger.error(f"  - {error}")
                return 1
            
            all_agency_indexes.append(agency_index)
            logger.info(f"{agency_name}: Loaded {file_count} projects")
        else:
            logger.info(f"{agency_name}: No project files found")
        
    
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
    global SCHEMA_VERSION, VALID_AGENCIES
    
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    logger.info("Starting consolidation of agency indexes...")
    
    # Initialize schema configuration from remote source
    logger.info("Initializing schema configuration from remote source")
    result = initialize_schema_config(AGENCY_INDEX_URL)
    if not result:
        logger.error("Cannot proceed without schema configuration")
        return 1
    
    SCHEMA_VERSION, VALID_AGENCIES = result
    
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
