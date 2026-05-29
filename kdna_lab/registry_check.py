"""KDNA Lab — Registry Integrity Validator.

Validates the KDNA registry index (domains.json) structure, required fields,
and domain entry completeness. Connects to the live registry.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner


# Required fields for each domain entry in the registry
REQUIRED_DOMAIN_FIELDS = [
    "name", "type", "version", "spec_version", "status", "access",
    "description", "core_insight", "author", "license",
    "quality_badge", "risk_level", "review_status",
    "provenance_required", "signature_required", "deprecated", "yanked",
    "created", "updated",
]
RECOMMENDED_DOMAIN_FIELDS = [
    "languages", "default_language", "i18n_level", "known_limitations_url",
    "file_count", "test_count", "judgment_version",
]
VALID_TYPES = {"domain", "cluster"}
VALID_STATUSES = {"draft", "experimental", "beta", "stable", "deprecated"}
VALID_QUALITY_BADGES = {"untested", "tested", "validated", "expert_reviewed", "production_ready"}
VALID_RISK_LEVELS = {"R0", "R1", "R2", "R3"}
VALID_MEDIA_TYPE = "application/vnd.aikdna.kdna+zip"


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
        if field not in entry or entry[field] is None or entry[field] == "":
            errors.append({"domain": name, "field": field, "error": f"Missing required field: {field}"})

    if entry.get("status") and entry["status"] not in VALID_STATUSES:
        errors.append({"domain": name, "field": "status", "error": f"Invalid status '{entry['status']}'"})

    if entry.get("type") and entry["type"] not in VALID_TYPES:
        errors.append({"domain": name, "field": "type", "error": f"Invalid type '{entry['type']}'"})

    if entry.get("spec_version") != "1.0-rc":
        errors.append({"domain": name, "field": "spec_version", "error": "spec_version must be 1.0-rc"})

    if entry.get("quality_badge") and entry["quality_badge"] not in VALID_QUALITY_BADGES:
        errors.append({"domain": name, "field": "quality_badge", "error": f"Invalid quality_badge '{entry['quality_badge']}'"})

    if entry.get("risk_level") and entry["risk_level"] not in VALID_RISK_LEVELS:
        errors.append({"domain": name, "field": "risk_level", "error": f"Invalid risk_level '{entry['risk_level']}'"})

    if not entry.get("name", "").startswith("@"):
        errors.append({"domain": name, "field": "name", "error": "Domain name must start with @"})

    for field in RECOMMENDED_DOMAIN_FIELDS:
        if field not in entry or entry[field] is None or entry[field] == "":
            warnings.append({"domain": name, "field": field, "error": f"Missing recommended field: {field}"})

    if entry.get("keywords"):
        if not isinstance(entry["keywords"], list):
            errors.append({"domain": name, "field": "keywords", "error": "keywords must be a list"})

    if entry.get("asset_url"):
        if not str(entry["asset_url"]).startswith("https://"):
            errors.append({"domain": name, "field": "asset_url", "error": "asset_url must be https://"})
        if entry.get("media_type") != VALID_MEDIA_TYPE:
            errors.append({"domain": name, "field": "media_type", "error": f"media_type must be {VALID_MEDIA_TYPE}"})
        digest = entry.get("asset_digest", "")
        if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
            errors.append({"domain": name, "field": "asset_digest", "error": "asset_digest must be sha256:<64 hex>"})

    if entry.get("yanked") is True:
        if not entry.get("yanked_reason"):
            errors.append({"domain": name, "field": "yanked_reason", "error": "yanked entries require yanked_reason"})
        if not entry.get("yanked_at"):
            errors.append({"domain": name, "field": "yanked_at", "error": "yanked entries require yanked_at"})
    elif entry.get("type") == "domain":
        for field in ("asset_url", "asset_digest", "media_type", "signature", "content_digest"):
            if not entry.get(field):
                errors.append({"domain": name, "field": field, "error": f"Non-yanked domain missing {field}"})

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
    """Refresh and load the canonical registry cache used by the live kdna CLI."""
    import subprocess
    cache_path = Path.home() / ".kdna" / "registry" / "domains.json"
    result = subprocess.run(["kdna", "registry", "refresh"], capture_output=True, text=True)
    if result.returncode != 0 and not cache_path.exists():
        raise RuntimeError(f"Failed to refresh registry: {result.stderr}")
    if not cache_path.exists():
        raise RuntimeError(f"Registry cache not found: {cache_path}")
    return load_registry_from_file(cache_path) or []


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
        "type": d.get("type"),
        "yanked": d.get("yanked"),
        "asset_url": bool(d.get("asset_url")),
        "asset_digest": bool(d.get("asset_digest")),
        "media_type": d.get("media_type"),
        "keywords": len(d.get("keywords", [])),
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
        installable = "yanked" if d["yanked"] else "installable"
        print(f"  {d['name']} v{d['version']} [{d['status']}/{installable}] type={d['type']} asset={d['asset_url']} media={d['media_type'] or '-'}")
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
