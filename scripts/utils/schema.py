"""Schema fetching and validation utilities for agency index processing."""

import json
import logging
import urllib.error
import urllib.request
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

# Schema configuration
SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URL = "https://gsa-share-it.github.io/codejson-schemas/schemas/agency-index"


def get_schema_url(version: str = SCHEMA_VERSION) -> str:
    """
    Get the full URL for a schema version.
    
    Args:
        version: Schema version (default: 1.0.0)
        
    Returns:
        Full URL to the schema
    """
    return f"{SCHEMA_BASE_URL}/schema-{version}.json"


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
            version = SCHEMA_VERSION
        
        # Extract from the version description if available
        version_desc = schema.get('properties', {}).get('version', {}).get('description', '')
        # Try to parse version from description like "version of the metadata schema in use..."
        if 'version' in version_desc.lower():
            # Fallback to default if explicit version not found
            version = SCHEMA_VERSION
        
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


def initialize_schema_config(url: str | None = None) -> tuple[str, set] | None:
    """
    Fetch and extract schema configuration.
    
    Args:
        url: Optional URL to schema. If not provided, uses get_schema_url()
        
    Returns:
        Tuple of (version, valid_agencies), or None if initialization fails
    """
    if url is None:
        url = get_schema_url()
    
    schema = fetch_schema(url)
    if not schema:
        logger.error("Failed to fetch schema. Please check your internet connection.")
        return None
    
    result = extract_schema_config(schema)
    if not result:
        logger.error("Failed to extract configuration from schema")
        return None
    
    return result


def validate_agency_index(index: dict, version: str, agencies: set) -> tuple[bool, list]:
    """
    Validate an agency index object against schema requirements using jsonschema.
    
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


def validate_agency_indexes(indexes: list, version: str, agencies: set) -> tuple[bool, list]:
    """
    Validate a list of agency indexes against schema requirements using jsonschema.
    
    Args:
        indexes: List of agency index objects
        version: Expected schema version
        agencies: Set of valid agency acronyms
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    all_errors = []
    
    # Validate that input is array
    if not isinstance(indexes, list):
        return False, [f"Input must be array, got {type(indexes).__name__}"]
    
    if len(indexes) == 0:
        return False, ["No agency indexes to validate"]
    
    # Validate each agency index
    for idx, agency_index in enumerate(indexes):
        if not isinstance(agency_index, dict):
            all_errors.append(f"Index {idx}: Expected object, got {type(agency_index).__name__}")
            continue
        
        is_valid, errors = validate_agency_index(agency_index, version, agencies)
        
        if not is_valid:
            agency_name = agency_index.get("agency", "UNKNOWN")
            error_prefix = f"Index {idx} ({agency_name})"
            all_errors.append(f"{error_prefix}: {len(errors)} validation error(s)")
            for error in errors:
                all_errors.append(f"  - {error}")
    
    return len(all_errors) == 0, all_errors
