"""Schema fetching and validation utilities for agency index and project record processing."""

import copy
import json
import logging
import urllib.request

from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

# Schema caching
_schema_cache = {}


def fetch_schema(url: str) -> dict:
    """
    Fetch and cache a JSON schema from the given URL.
    
    Returns the cached schema if already fetched.
    
    Args:
        url: Full URL to the schema
        
    Returns:
        Parsed schema dictionary
    """
    if url in _schema_cache:
        return copy.deepcopy(_schema_cache[url])
    
    logger.debug(f"Fetching schema from {url}")
    with urllib.request.urlopen(url, timeout=10) as response:
        schema = json.loads(response.read().decode('utf-8'))
    
    _schema_cache[url] = copy.deepcopy(schema)
    return schema


def extract_schema_config(schema: dict) -> tuple[str, set]:
    """
    Extract version and valid agencies from the schema.
    
    Args:
        schema: Parsed schema dictionary
        
    Returns:
        Tuple of (version, valid_agencies_set)
    """
    # Extract version
    version = schema.get('properties', {}).get('version', {}).get('type')
    if not version:
        version = AGENCY_INDEX_VERSION
    
    # Extract agency enum values
    agency_enum = schema.get('properties', {}).get('agency', {}).get('enum', [])
    valid_agencies = set(agency_enum)
    
    logger.info(f"Schema version: {version}, agencies: {len(valid_agencies)}")
    
    return version, valid_agencies


def initialize_schema_config(url: str) -> tuple[str, set]:
    """
    Fetch and extract schema configuration.
    
    Args:
        url: URL to the agency index schema
        
    Returns:
        Tuple of (version, valid_agencies)
    """
    schema = fetch_schema(url)
    return extract_schema_config(schema)


def validate_agency_index(index: dict, version: str, agencies: set) -> tuple[bool, list]:
    """
    Validate an agency index object against schema requirements.
    
    Validates:
    - 'version' field is present and matches expected version
    - 'agency' field is present and is a valid agency acronym
    - 'releases' field is present and is an array
    
    Args:
        index: The agency index object to validate
        version: Expected schema version
        agencies: Set of valid agency acronyms
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Create a minimal schema for required fields validation
    schema = {
        "type": "object",
        "required": ["version", "agency", "releases"],
        "properties": {
            "version": {
                "type": "string",
                "const": version
            },
            "agency": {
                "type": "string",
                "enum": list(agencies)
            },
            "releases": {
                "type": "array"
            }
        }
    }
    
    try:
        validate(instance=index, schema=schema)
        return True, []
    except ValidationError as e:
        # Format jsonschema ValidationError for readability
        if e.validator == "required":
            missing = set(e.schema.get("required", [])) - set(index.keys())
            for field in missing:
                errors.append(f"Missing required field: '{field}'")
        elif e.validator == "const":
            errors.append(f"Field '{e.path[-1] if e.path else 'version'}' must be '{e.schema.get('const')}', got '{index.get('version')}'")
        elif e.validator == "enum":
            errors.append(f"Field '{e.path[-1] if e.path else 'agency'}' must be one of {e.schema.get('enum')}, got '{index.get('agency')}'")
        elif e.validator == "type":
            field_path = list(e.path)[-1] if e.path else "unknown"
            actual_type = type(e.instance).__name__
            expected_type = e.schema.get("type", "unknown")
            errors.append(f"Field '{field_path}' must be {expected_type}, got {actual_type}")
        else:
            errors.append(str(e.message))
        
        return False, errors


def clear_schema_cache():
    """Clear the schema cache. Useful for testing or forcing a refresh."""
    global _schema_cache
    _schema_cache.clear()
    logger.debug("Schema cache cleared")
