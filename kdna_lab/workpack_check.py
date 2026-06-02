"""KDNA Lab — Work Pack Validator.

Validates KDNA Work Pack manifests against the Work Pack schema,
checks structural completeness, and cross-validates registry entries.

Uses the official schemas from OPEN_SOURCE/kdna-workpack/specs/.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kdna_lab.paths import LAB_ROOT


# Work Pack schema file list
WORKPACK_SCHEMA_FILES = [
    "work-pack.schema.json",
    "work-pack-skill-binding.schema.json",
    "work-pack-review-gate.schema.json",
    "work-pack-risk-policy.schema.json",
    "work-pack-trace-policy.schema.json",
]


def resolve_workpack_dir() -> Path:
    """Resolve the Work Pack repository directory."""
    env = os.environ.get("KDNA_WORKPACK_DIR")
    if env:
        return Path(env)

    candidates = [
        LAB_ROOT.parent.parent / "OPEN_SOURCE" / "kdna-workpack",
        LAB_ROOT.parent / "OPEN_SOURCE" / "kdna-workpack",
    ]
    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        "Cannot find kdna-workpack directory. Set KDNA_WORKPACK_DIR env var."
    )


def resolve_schemas_dir() -> Path:
    """Resolve the Work Pack specs directory."""
    return resolve_workpack_dir() / "specs"


def discover_workpacks(workpack_dir: Path) -> List[Dict]:
    """Discover all Work Packs in the examples directory."""
    examples_dir = workpack_dir / "examples" / "work-packs"
    if not examples_dir.exists():
        return []

    results = []
    for entry in sorted(examples_dir.iterdir()):
        if not entry.is_dir():
            continue
        wp_path = entry / "workpack.json"
        if wp_path.exists():
            try:
                manifest = json.loads(wp_path.read_text())
                results.append({
                    "name": entry.name,
                    "path": str(entry),
                    "manifest": manifest,
                })
            except (json.JSONDecodeError, KeyError):
                pass
    return results


def load_schema(schemas_dir: Path, name: str) -> Optional[Dict]:
    """Load a JSON schema file."""
    path = schemas_dir / name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def validate_workpack_manifest(manifest: Dict) -> Tuple[bool, List[str]]:
    """Validate a Work Pack manifest against basic rules.

    Since Python doesn't have ajv-equivalent easily, we do structural checks:
    - Required fields present
    - Enum values valid
    - Pattern matches for names
    """
    errors = []

    # Required fields
    for field in ["format", "format_version", "name", "version", "description", "status", "kdna"]:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    # Format check
    if manifest.get("format") != "kdna-workpack":
        errors.append(f"Invalid format: {manifest.get('format')} (expected 'kdna-workpack')")

    # Status enum
    valid_statuses = {"draft", "experimental", "stable", "deprecated"}
    if manifest.get("status") not in valid_statuses:
        errors.append(f"Invalid status: {manifest.get('status')} (must be one of {valid_statuses})")

    # Access enum
    valid_access = {"open", "licensed", "runtime", "enterprise", "partner"}
    if manifest.get("access") and manifest["access"] not in valid_access:
        errors.append(f"Invalid access: {manifest['access']}")

    # Name pattern
    import re
    name = manifest.get("name", "")
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        errors.append(f"Invalid name format: {name} (must be kebab-case)")

    # Version semver
    version = manifest.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+", version):
        errors.append(f"Invalid version format: {version} (must be semver)")

    # KDNA section
    kdna = manifest.get("kdna", {})
    mode = kdna.get("mode")
    if mode not in ("single", "cluster"):
        errors.append(f"Invalid kdna.mode: {mode} (must be 'single' or 'cluster')")

    if mode == "single":
        asset = kdna.get("asset", {})
        for f in ["name", "version", "role"]:
            if f not in asset:
                errors.append(f"Missing kdna.asset.{f}")
        role = asset.get("role")
        if role and role not in ("primary", "constraint", "fallback"):
            errors.append(f"Invalid kdna.asset.role: {role}")
    elif mode == "cluster":
        assets = kdna.get("assets", [])
        if not isinstance(assets, list) or len(assets) < 2:
            errors.append("kdna.mode='cluster' requires at least 2 assets")
        for i, a in enumerate(assets):
            for f in ["name", "version", "role"]:
                if f not in a:
                    errors.append(f"Missing kdna.assets[{i}].{f}")

    # Skills
    skills = manifest.get("skills", [])
    for i, s in enumerate(skills):
        if "name" not in s:
            errors.append(f"Missing skills[{i}].name")

    return len(errors) == 0, errors


def check_workpack_structure(manifest: Dict, root_dir: Path) -> Tuple[bool, List[str]]:
    """Check that all referenced files in the Work Pack exist."""
    missing = []
    refs = []

    templates = manifest.get("templates", {})
    if templates:
        if templates.get("task"):
            refs.append(templates["task"])
        if templates.get("output"):
            refs.append(templates["output"])

    for g in manifest.get("review_gates", []):
        refs.append(g)

    for key in ["risk_policy", "trace_policy", "evals"]:
        val = manifest.get(key)
        if val:
            refs.append(val)

    for ref in refs:
        if not (root_dir / ref).exists():
            missing.append(ref)

    return len(missing) == 0, missing


def validate_registry_entry(entry: Dict, workpack_dir: Path) -> Tuple[bool, List[str]]:
    """Validate a registry entry against its source Work Pack manifest."""
    errors = []

    source = entry.get("source")
    if not source:
        errors.append("Missing 'source' field")
        return False, errors

    source_path = workpack_dir / source
    if not source_path.exists():
        errors.append(f"Source directory not found: {source}")
        return False, errors

    wp_path = source_path / "workpack.json"
    if not wp_path.exists():
        errors.append(f"workpack.json not found in {source}")
        return False, errors

    try:
        manifest = json.loads(wp_path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in workpack.json: {e}")
        return False, errors

    # Cross-check name
    if manifest.get("name") != entry.get("name"):
        errors.append(f"Name mismatch: registry={entry.get('name')}, manifest={manifest.get('name')}")

    # Cross-check version
    if manifest.get("version") != entry.get("version"):
        errors.append(f"Version mismatch: registry={entry.get('version')}, manifest={manifest.get('version')}")

    # Cross-check gate count
    actual_gates = len(manifest.get("review_gates", []))
    declared_gates = entry.get("review_gates")
    if declared_gates is not None and actual_gates != declared_gates:
        errors.append(f"Gate count mismatch: registry={declared_gates}, actual={actual_gates}")

    # Cross-check skills
    skills = manifest.get("skills", [])
    required_skills = [s["name"] for s in skills if s.get("required", True)]
    optional_skills = [s["name"] for s in skills if not s.get("required", True)]

    reg_required = set(entry.get("skills_required", []))
    reg_optional = set(entry.get("skills_optional", []))

    if reg_required != set(required_skills):
        errors.append(f"Skills required mismatch: registry={sorted(reg_required)}, actual={sorted(required_skills)}")
    if reg_optional != set(optional_skills):
        errors.append(f"Skills optional mismatch: registry={sorted(reg_optional)}, actual={sorted(optional_skills)}")

    # Cross-check risk/trace policy
    if entry.get("has_risk_policy") != bool(manifest.get("risk_policy")):
        errors.append(f"has_risk_policy mismatch")
    if entry.get("has_trace_policy") != bool(manifest.get("trace_policy")):
        errors.append(f"has_trace_policy mismatch")

    return len(errors) == 0, errors


def run_workpack_checks(workpack_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Run all Work Pack validation checks.

    Returns a structured result dict with summary, per-workpack results,
    and registry validation results.
    """
    if workpack_dir is None:
        workpack_dir = resolve_workpack_dir()

    schemas_dir = workpack_dir / "specs"
    registry_path = workpack_dir / "registry" / "workpacks.json"

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workpack_dir": str(workpack_dir),
        "schemas_available": [],
        "workpacks": [],
        "registry": None,
        "summary": {
            "total": 0, "schema_pass": 0, "schema_fail": 0,
            "structure_pass": 0, "structure_fail": 0,
            "registry_pass": 0, "registry_fail": 0,
        },
    }

    # Check available schemas
    for schema_file in WORKPACK_SCHEMA_FILES:
        if (schemas_dir / schema_file).exists():
            results["schemas_available"].append(schema_file)

    # Discover and validate Work Packs
    workpacks = discover_workpacks(workpack_dir)
    for wp in workpacks:
        wp_result = {
            "name": wp["name"],
            "version": wp["manifest"].get("version", "?"),
            "schema_valid": False,
            "schema_errors": [],
            "structure_complete": False,
            "structure_missing": [],
        }

        schema_ok, schema_errors = validate_workpack_manifest(wp["manifest"])
        wp_result["schema_valid"] = schema_ok
        wp_result["schema_errors"] = schema_errors

        if schema_ok:
            struct_ok, struct_missing = check_workpack_structure(
                wp["manifest"], Path(wp["path"])
            )
            wp_result["structure_complete"] = struct_ok
            wp_result["structure_missing"] = struct_missing

        results["workpacks"].append(wp_result)
        results["summary"]["total"] += 1
        if schema_ok:
            results["summary"]["schema_pass"] += 1
        else:
            results["summary"]["schema_fail"] += 1
        if wp_result["structure_complete"]:
            results["summary"]["structure_pass"] += 1
        else:
            results["summary"]["structure_fail"] += 1

    # Validate registry
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except json.JSONDecodeError:
            registry = None

        if registry:
            reg_results = {
                "format": registry.get("format"),
                "entries": [],
                "passed": 0,
                "failed": 0,
            }
            for entry in registry.get("workpacks", []):
                ok, errors = validate_registry_entry(entry, workpack_dir)
                reg_results["entries"].append({
                    "name": entry.get("name"),
                    "valid": ok,
                    "errors": errors,
                })
                if ok:
                    reg_results["passed"] += 1
                else:
                    reg_results["failed"] += 1

            results["registry"] = reg_results
            results["summary"]["registry_pass"] = reg_results["passed"]
            results["summary"]["registry_fail"] = reg_results["failed"]

    return results


def print_results(results: Dict[str, Any], json_mode: bool = False) -> None:
    """Print validation results in human-readable or JSON format."""
    if json_mode:
        print(json.dumps(results, indent=2, default=str))
        return

    summary = results["summary"]
    print("═══════════════════════════════════════════════════")
    print("  KDNA Lab — Work Pack Validation")
    print("═══════════════════════════════════════════════════")
    print(f"  Directory: {results['workpack_dir']}")
    print(f"  Schemas:   {len(results['schemas_available'])} available")
    print(f"  Work Packs: {summary['total']} discovered")
    print()

    # Schema results
    print(f"── Schema (L0) ──")
    for wp in results["workpacks"]:
        icon = "✅" if wp["schema_valid"] else "❌"
        print(f"  {icon} {wp['name']} v{wp['version']}")
        for e in wp["schema_errors"]:
            print(f"     {e}")
    print()

    # Structure results
    print(f"── Structure (L1) ──")
    for wp in results["workpacks"]:
        if not wp["schema_valid"]:
            continue
        icon = "✅" if wp["structure_complete"] else "❌"
        print(f"  {icon} {wp['name']} — {'complete' if wp['structure_complete'] else 'incomplete'}")
        for m in wp["structure_missing"]:
            print(f"     Missing: {m}")
    print()

    # Registry results
    if results["registry"]:
        reg = results["registry"]
        print(f"── Registry ({reg['passed']}/{reg['passed'] + reg['failed']} valid) ──")
        for e in reg["entries"]:
            icon = "✅" if e["valid"] else "❌"
            print(f"  {icon} {e['name']}")
            for err in e["errors"]:
                print(f"     {err}")
        print()

    print("═══════════════════════════════════════════════════")
    total = summary["schema_pass"] + summary["structure_pass"] + summary.get("registry_pass", 0)
    fails = summary["schema_fail"] + summary["structure_fail"] + summary.get("registry_fail", 0)
    print(f"  Results: {total} passed, {fails} failed")
    print("═══════════════════════════════════════════════════")


def workpack_check_cli() -> None:
    """CLI entry point: kdna-lab-workpack."""
    import argparse

    parser = argparse.ArgumentParser(description="KDNA Lab — Work Pack Validator")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--dir", type=str, help="Path to kdna-workpack directory")
    parser.add_argument("--schema-only", action="store_true", help="Only run schema validation (L0)")
    parser.add_argument("--registry-only", action="store_true", help="Only validate registry entries")
    args = parser.parse_args()

    workpack_dir = Path(args.dir) if args.dir else None

    try:
        if workpack_dir is None:
            workpack_dir = resolve_workpack_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    results = run_workpack_checks(workpack_dir)
    print_results(results, json_mode=args.json)

    # Exit code based on failures
    summary = results["summary"]
    fails = summary["schema_fail"] + summary["structure_fail"] + summary.get("registry_fail", 0)
    sys.exit(1 if fails > 0 else 0)


if __name__ == "__main__":
    workpack_check_cli()
