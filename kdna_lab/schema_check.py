"""KDNA Lab — Domain Schema Validator.

Validates KDNA domain files against the official JSON schemas defined
in the KDNA protocol specification (SPEC).

Uses the official schemas from OPEN_SOURCE/kdna/schema/ to validate
KDNA_Core.json, KDNA_Patterns.json, KDNA_Scenarios.json, and kdna.json.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kdna_lab.paths import LAB_ROOT


SCHEMA_FILE_MAP = {
    "KDNA_Core.json": "KDNA_Core.schema.json",
    "KDNA_Patterns.json": "KDNA_Patterns.schema.json",
    "KDNA_Scenarios.json": "KDNA_Scenarios.schema.json",
    "KDNA_Cases.json": "KDNA_Cases.schema.json",
    "KDNA_Reasoning.json": "KDNA_Reasoning.schema.json",
    "KDNA_Evolution.json": "KDNA_Evolution.schema.json",
    "KDNA_Cluster.json": "KDNA_Cluster.schema.json",
    "kdna.json": "kdna-file.schema.json",
}


def resolve_schema_dir() -> Path:
    """Resolve the official KDNA schema directory.

    Priority:
    1. KDNA_SCHEMA_DIR env var
    2. OPEN_SOURCE/kdna/schema/ (sibling of kdna-lab)
    """
    env = os.environ.get("KDNA_SCHEMA_DIR")
    if env:
        return Path(env)

    candidates = [
        LAB_ROOT.parent.parent / "OPEN_SOURCE" / "kdna" / "schema",
        LAB_ROOT.parent / "OPEN_SOURCE" / "kdna" / "schema",
    ]
    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        "Cannot find KDNA schema directory. Set KDNA_SCHEMA_DIR env var "
        "or ensure OPEN_SOURCE/kdna/schema/ exists relative to KDNALAB/."
    )


def load_schema(schemas_dir: Path, schema_name: str) -> Optional[Dict]:
    """Load a JSON schema file."""
    path = schemas_dir / schema_name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def validate_with_schema(instance: Dict, schema: Dict) -> List[str]:
    """Validate a JSON instance against a JSON schema.

    Returns list of error messages (empty = valid).
    Uses a minimal subset of JSON Schema validation sufficient for KDNA.
    """
    errors = []

    if schema.get("type") and schema["type"] != "object":
        return errors

    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required_fields:
        if field not in instance or instance[field] is None:
            errors.append(f"Missing required field: {field}")

    for field, prop_schema in properties.items():
        if field not in instance:
            continue

        value = instance[field]
        expected_type = prop_schema.get("type")

        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{field}': expected string, got {type(value).__name__}")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{field}': expected number, got {type(value).__name__}")
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append(f"Field '{field}': expected integer, got {type(value).__name__}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{field}': expected boolean, got {type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field}': expected array, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field}': expected object, got {type(value).__name__}")

        if "enum" in prop_schema and value not in prop_schema["enum"]:
            errors.append(f"Field '{field}': value '{value}' not in enum {prop_schema['enum']}")

        if expected_type == "array" and isinstance(value, list) and "items" in prop_schema:
            item_type = prop_schema["items"].get("type")
            for i, item in enumerate(value):
                if item_type == "string" and not isinstance(item, str):
                    errors.append(f"Field '{field}[{i}]': expected string, got {type(item).__name__}")
                elif item_type == "object" and not isinstance(item, dict):
                    errors.append(f"Field '{field}[{i}]': expected object, got {type(item).__name__}")

    return errors


def validate_domain_file(file_path: Path, schemas_dir: Path) -> Dict[str, Any]:
    """Validate a single KDNA domain JSON file against its schema."""
    file_name = file_path.name
    schema_name = SCHEMA_FILE_MAP.get(file_name)

    result = {
        "file": str(file_path),
        "valid": True,
        "errors": [],
        "schema_matched": schema_name is not None,
    }

    if file_name.endswith(".schema.json"):
        result["errors"].append("Skipped: schema file, not a domain file")
        return result

    if not schema_name:
        result["errors"].append(f"No schema mapping for {file_name}")
        return result

    schema = load_schema(schemas_dir, schema_name)
    if schema is None:
        result["errors"].append(f"Schema file not found: {schema_name}")
        return result

    try:
        instance = json.loads(file_path.read_text())
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"Invalid JSON: {e}")
        return result

    validation_errors = validate_with_schema(instance, schema)
    if validation_errors:
        result["valid"] = False
        result["errors"].extend(validation_errors)

    return result


def validate_domain_directory(domain_dir: Path, schemas_dir: Path) -> List[Dict[str, Any]]:
    """Validate all JSON files in a domain directory."""
    results = []
    for json_file in sorted(domain_dir.glob("*.json")):
        result = validate_domain_file(json_file, schemas_dir)
        results.append(result)
    return results


def validate_all_fixtures(fixtures_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Validate all domain fixtures against official schemas."""
    if fixtures_dir is None:
        fixtures_dir = LAB_ROOT / "fixtures"
    schemas_dir = resolve_schema_dir()

    all_results = []
    for fixture_dir in sorted(fixtures_dir.iterdir()):
        if not fixture_dir.is_dir():
            continue
        domain_results = validate_domain_directory(fixture_dir, schemas_dir)
        all_results.append({
            "domain": fixture_dir.name,
            "path": str(fixture_dir),
            "files": domain_results,
            "passed": all(r["valid"] for r in domain_results),
        })

    return all_results


def validate_installed_domains(kdna_home: Path | None = None) -> List[Dict[str, Any]]:
    """Validate all installed KDNA domains against official schemas."""
    if kdna_home is None:
        kdna_home = Path.home() / ".kdna"

    schemas_dir = resolve_schema_dir()
    domains_dir = kdna_home / "cache" / "domains"
    if not domains_dir.exists():
        return []

    all_results = []
    for domain_dir in sorted(domains_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        domain_results = validate_domain_directory(domain_dir, schemas_dir)
        all_results.append({
            "domain": domain_dir.name,
            "path": str(domain_dir),
            "files": domain_results,
            "passed": all(r["valid"] for r in domain_results),
        })

    return all_results


def print_schema_report(results: List[Dict[str, Any]]):
    """Print a human-readable schema validation report."""
    total_domains = len(results)
    passed = sum(1 for r in results if r["passed"])
    total_files = sum(len(r["files"]) for r in results)
    total_errors = sum(
        len(f["errors"]) for r in results for f in r["files"] if not f["valid"]
    )

    print(f"\n{'='*60}")
    print(f"KDNA Domain Schema Validation Report")
    print(f"{'='*60}")
    print(f"Total domains: {total_domains}")
    print(f"Passed: {passed}")
    print(f"Failed: {total_domains - passed}")
    print(f"Total files checked: {total_files}")
    print(f"Total errors: {total_errors}")
    print()

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['domain']}")
        for f in r["files"]:
            f_status = "OK" if f["valid"] else "ERR"
            file_name = Path(f["file"]).name
            if f["errors"]:
                print(f"    {f_status} {file_name}")
                for err in f["errors"]:
                    print(f"      - {err}")
    print()


def schema_check_cli():
    """CLI entry point for schema validation."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Domain Schema Validator")
    parser.add_argument("--fixtures", action="store_true", default=True, help="Validate fixture domains")
    parser.add_argument("--installed", action="store_true", help="Validate installed domains")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.installed:
        results = validate_installed_domains()
    else:
        results = validate_all_fixtures()

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_schema_report(results)


if __name__ == "__main__":
    schema_check_cli()
