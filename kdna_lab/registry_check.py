"""KDNA Lab — Registry Integrity Validator.

Validates the KDNA registry index (domains.json) structure, required fields,
and domain entry completeness. Connects to the live registry.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner


# Required fields for each domain entry in the registry
REQUIRED_DOMAIN_FIELDS = [
    "name", "version", "status", "description",
]
RECOMMENDED_DOMAIN_FIELDS = [
    "judgment_version", "core_insight", "keywords",
    "applies_when", "does_not_apply_when", "failure_risks",
]
VALID_STATUSES = ["experimental", "stable", "deprecated", "yanked"]


@dataclass
class RegistryCheckResult:
    passed: bool
    total_domains: int = 0
    valid_domains: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


def validate_registry_entry(entry: Dict, index: int) -> Tuple[List[Dict], List[Dict]]:
    """Validate a single registry domain entry. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if not isinstance(entry, dict):
        errors.append({"domain": f"entry_{index}", "field": "(root)", "error": "Entry is not a JSON object"})
        return errors, warnings

    name = entry.get("name", f"entry_{index}")

    for field in REQUIRED_DOMAIN_FIELDS:
        if field not in entry or not entry[field]:
            errors.append({"domain": name, "field": field, "error": f"Missing required field: {field}"})

    if entry.get("status") and entry["status"] not in VALID_STATUSES:
        errors.append({"domain": name, "field": "status", "error": f"Invalid status '{entry['status']}'"})

    if not entry.get("name", "").startswith("@"):
        errors.append({"domain": name, "field": "name", "error": "Domain name must start with @"})

    for field in RECOMMENDED_DOMAIN_FIELDS:
        if field not in entry or not entry[field]:
            warnings.append({"domain": name, "field": field, "error": f"Missing recommended field: {field}"})

    if entry.get("keywords"):
        if not isinstance(entry["keywords"], list):
            errors.append({"domain": name, "field": "keywords", "error": "keywords must be a list"})

    if entry.get("applies_when"):
        if not isinstance(entry["applies_when"], list) or len(entry["applies_when"]) == 0:
            warnings.append({"domain": name, "field": "applies_when", "error": "applies_when should be a non-empty list"})

    if entry.get("failure_risks"):
        if not isinstance(entry["failure_risks"], list) or len(entry["failure_risks"]) == 0:
            warnings.append({"domain": name, "field": "failure_risks", "error": "failure_risks should be a non-empty list"})

    return errors, warnings


def validate_registry_index(registry_data: List[Dict]) -> RegistryCheckResult:
    """Validate the entire registry index."""
    result = RegistryCheckResult(passed=True, total_domains=len(registry_data))

    if not isinstance(registry_data, list):
        result.errors.append({"domain": "(root)", "field": "(root)", "error": "Registry data is not a JSON array"})
        result.passed = False
        return result

    if len(registry_data) == 0:
        result.warnings.append({"domain": "(root)", "field": "(root)", "error": "Registry is empty"})
        return result

    names_seen = set()
    for i, entry in enumerate(registry_data):
        errors, warnings = validate_registry_entry(entry, i)
        result.errors.extend(errors)
        result.warnings.extend(warnings)

        name = entry.get("name", f"entry_{i}")
        if name in names_seen:
            result.errors.append({"domain": name, "field": "name", "error": "Duplicate domain name in registry"})
        names_seen.add(name)

        if not errors:
            result.valid_domains += 1

    if result.errors:
        result.passed = False

    return result


def load_registry_from_file(path: str | Path) -> List[Dict] | None:
    """Load registry data from a local JSON file.

    Handles both raw arrays and wrapped objects with a 'domains' key.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid registry JSON: {e}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "domains" in data:
        return data["domains"]
    raise ValueError(f"Unrecognized registry format in {path}: expected array or {{domains: [...]}}")


def load_registry_from_live() -> List[Dict]:
    """Load registry data from the live kdna CLI."""
    import subprocess
    result = subprocess.run(
        ["kdna", "available", "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch registry: {result.stderr}")
    return json.loads(result.stdout)


def check_registry(live: bool = True, local_path: str | None = None) -> RegistryCheckResult:
    """Run full registry integrity check.

    Args:
        live: If True, fetches from live kdna CLI
        local_path: Path to local domains.json file
    """
    if live:
        try:
            data = load_registry_from_live()
        except RuntimeError as e:
            result = RegistryCheckResult(passed=False)
            result.errors.append({"domain": "(root)", "field": "(root)", "error": str(e)})
            return result
    elif local_path:
        data = load_registry_from_file(local_path)
        if data is None:
            result = RegistryCheckResult(passed=False)
            result.errors.append({"domain": "(root)", "field": "(root)", "error": f"File not found: {local_path}"})
            return result
    else:
        result = RegistryCheckResult(passed=False)
        result.errors.append({"domain": "(root)", "field": "(root)", "error": "No data source specified"})
        return result

    result = validate_registry_index(data)

    result.details = [{
        "name": d.get("name"),
        "version": d.get("version"),
        "status": d.get("status"),
        "keywords": len(d.get("keywords", [])),
        "applies_when_count": len(d.get("applies_when", [])),
        "failure_risks_count": len(d.get("failure_risks", [])),
    } for d in data]

    return result


def print_registry_report(result: RegistryCheckResult):
    """Print a human-readable registry validation report."""
    print(f"\n{'='*60}")
    print(f"KDNA Registry Integrity Report")
    print(f"{'='*60}")
    print(f"Status: {'PASS' if result.passed else 'FAIL'}")
    print(f"Total domains: {result.total_domains}")
    print(f"Valid domains: {result.valid_domains}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    if result.errors:
        print(f"\n--- Errors ---")
        for e in result.errors:
            print(f"  [{e['domain']}] {e['field']}: {e['error']}")

    if result.warnings:
        print(f"\n--- Warnings ---")
        for w in result.warnings[:10]:
            print(f"  [{w['domain']}] {w['field']}: {w['error']}")
        if len(result.warnings) > 10:
            print(f"  ... and {len(result.warnings) - 10} more")

    print(f"\n--- Domain Summary ---")
    for d in result.details:
        print(f"  {d['name']} v{d['version']} [{d['status']}] kw={d['keywords']} aw={d['applies_when_count']} fr={d['failure_risks_count']}")
    print()


def registry_check_cli():
    """CLI entry point for registry check."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Registry Integrity Checker")
    parser.add_argument("--live", action="store_true", default=True, help="Check live registry via CLI")
    parser.add_argument("--file", default=None, help="Check local domains.json file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.file:
        result = check_registry(live=False, local_path=args.file)
    else:
        result = check_registry(live=args.live)

    if args.json:
        print(json.dumps({
            "passed": result.passed,
            "total_domains": result.total_domains,
            "valid_domains": result.valid_domains,
            "errors": result.errors,
            "warnings": result.warnings,
            "details": result.details,
        }, indent=2, ensure_ascii=False))
    else:
        print_registry_report(result)


if __name__ == "__main__":
    registry_check_cli()
