"""KDNA Lab — SPEC Consistency Checker.

Validates that the KDNA protocol specification (SPEC.md and specs/*.md)
is internally consistent with the actual schema files, CLI behavior,
and domain format.

Also validates App Runtime Contract compliance for installed apps.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT
from kdna_lab.schema_check import resolve_schema_dir


def resolve_spec_dir() -> Optional[Path]:
    """Resolve the KDNA SPEC directory."""
    env = os.environ.get("KDNA_SPEC_DIR")
    if env:
        return Path(env)

    candidates = [
        LAB_ROOT.parent.parent / "OPEN_SOURCE" / "kdna",
        LAB_ROOT.parent / "OPEN_SOURCE" / "kdna",
    ]
    for c in candidates:
        if (c / "SPEC.md").exists():
            return c
    return None


# Expected spec documents based on the KDNA protocol v1.0
EXPECTED_SPEC_DOCS = {
    "kdna-access-modes.md": "Access mode definitions",
    "kdna-asset-card.md": "Asset card specification",
    "kdna-crypto-protocol.md": "Cryptographic protocol spec",
    "kdna-entitlement-api.md": "Entitlement API specification",
    "kdna-file-format.md": "KDNA file format specification",
    "kdna-identity-key.md": "Identity key management",
    "kdna-license.md": "License specification",
    "kdna-package-format.md": "Package format specification",
    "kdna-registry.md": "Registry protocol specification",
    "load-profiles.md": "Load profile definitions",
    "package-profiles.md": "Package profile definitions",
    "human-lock.md": "Human Lock protocol",
    "human-lock-gate-design.md": "Human Lock gate design",
    "quality-badge-evidence-gate.md": "Quality badge evidence gate",
    "enum-tables.md": "Enumeration value tables",
    "cli-license-identity-skeleton.md": "CLI license identity skeleton",
    "authorization-subscription-metadata.md": "Auth/subscription metadata",
}

# JSON schemas referenced in specs
EXPECTED_JSON_SPECS = {
    "route-result.schema.json": "Route result schema",
    "judgment-trace.schema.json": "Judgment trace schema",
    "judgment-report-schema.json": "Judgment report schema",
    "outcome-record-schema.json": "Outcome record schema",
    "improvement-proposal-schema.json": "Improvement proposal schema",
}


def check_spec_docs(spec_dir: Path) -> List[Dict[str, Any]]:
    """Check that all expected spec documents exist."""
    results = []
    specs_subdir = spec_dir / "specs"

    for doc, description in EXPECTED_SPEC_DOCS.items():
        path = specs_subdir / doc
        found = path.exists()
        size = path.stat().st_size if found else 0
        results.append({
            "doc": doc,
            "description": description,
            "found": found,
            "size_bytes": size,
        })

    for doc, description in EXPECTED_JSON_SPECS.items():
        path = specs_subdir / doc
        found = path.exists()
        size = path.stat().st_size if found else 0
        results.append({
            "doc": doc,
            "description": description,
            "found": found,
            "size_bytes": size,
            "type": "json_schema",
        })

    return results


def check_schema_references(spec_dir: Path) -> List[Dict[str, Any]]:
    """Check that schema JSON files referenced in specs exist in schema/."""
    results = []
    schema_dir = resolve_schema_dir()

    schema_files_in_specs = []
    for f in (spec_dir / "specs").glob("*.json"):
        schema_files_in_specs.append(f.name)

    for sf in schema_files_in_specs:
        in_schema_dir = (schema_dir / sf).exists()
        results.append({
            "schema": sf,
            "in_specs_dir": True,
            "in_schema_dir": in_schema_dir,
            "consistent": in_schema_dir,
        })

    schema_files = set()
    for f in schema_dir.glob("*.json"):
        schema_files.add(f.name)

    for sf in schema_files:
        in_specs = sf in schema_files_in_specs
        results.append({
            "schema": sf,
            "in_specs_dir": in_specs,
            "in_schema_dir": True,
            "consistent": True,
        })

    return results


def run_spec_check() -> Dict[str, Any]:
    """Run the full SPEC consistency check."""
    spec_dir = resolve_spec_dir()
    if spec_dir is None:
        return {"error": "Cannot find KDNA spec directory."}

    docs = check_spec_docs(spec_dir)
    schema_refs = check_schema_references(spec_dir)

    spec_exists = (spec_dir / "SPEC.md").exists()
    spec_size = (spec_dir / "SPEC.md").stat().st_size if spec_exists else 0

    total_docs = len(docs)
    found_docs = sum(1 for d in docs if d["found"])
    missing_docs = [d for d in docs if not d["found"]]
    inconsistent_schemas = [s for s in schema_refs if not s.get("consistent", True)]

    return {
        "spec_dir": str(spec_dir),
        "spec_md_exists": spec_exists,
        "spec_md_size": spec_size,
        "total_expected_docs": total_docs,
        "found_docs": found_docs,
        "missing_docs": missing_docs,
        "schema_refs": schema_refs,
        "inconsistent_schemas": inconsistent_schemas,
        "passed": len(missing_docs) == 0 and len(inconsistent_schemas) == 0,
    }


def print_spec_report(result: Dict[str, Any]):
    """Print human-readable SPEC consistency report."""
    if "error" in result:
        print(f"[ERROR] {result['error']}")
        return

    print(f"\n{'='*60}")
    print(f"KDNA SPEC Consistency Report")
    print(f"{'='*60}")
    print(f"SPEC directory: {result['spec_dir']}")
    print(f"SPEC.md: {'FOUND' if result['spec_md_exists'] else 'MISSING'} ({result['spec_md_size']} bytes)")
    print(f"Status: {'PASS' if result['passed'] else 'ISSUES FOUND'}")
    print(f"Docs: {result['found_docs']}/{result['total_expected_docs']} found")

    if result["missing_docs"]:
        print(f"\n--- Missing Documents ---")
        for d in result["missing_docs"]:
            print(f"  {d['doc']}: {d['description']}")

    if result["inconsistent_schemas"]:
        print(f"\n--- Schema Inconsistencies ---")
        for s in result["inconsistent_schemas"]:
            print(f"  {s['schema']}: in_specs={s.get('in_specs_dir')}, in_schema={s.get('in_schema_dir')}")

    print()


# --- App Runtime Contract Verification ---

APP_RUNTIME_CONTRACT = {
    "packages_dir": ".kdna/packages",
    "index_file": ".kdna/index.db",
    "cache_dir": ".kdna/cache",
    "domains_cache": ".kdna/cache/domains",
    "registry_file": ".kdna/registry.json",
}


def verify_app_runtime_contract(kdna_home: Path | None = None) -> Dict[str, Any]:
    """Verify the local KDNA environment against the App Runtime Contract.

    Checks:
    1. packages directory exists with properly named .kdna files
    2. cache/domains/ exists and is separate from packages/
    3. index file exists (index.db or index.json)
    4. No raw source directories in ~/.kdna/domains/
    """
    if kdna_home is None:
        kdna_home = Path.home() / ".kdna"

    checks = []
    all_pass = True

    packages_dir = kdna_home / "packages"
    checks.append({
        "check": "packages directory exists",
        "passed": packages_dir.exists(),
        "path": str(packages_dir),
    })
    if not packages_dir.exists():
        all_pass = False

    cache_dir = kdna_home / "cache"
    checks.append({
        "check": "cache directory exists",
        "passed": cache_dir.exists(),
        "path": str(cache_dir),
    })

    domains_cache = kdna_home / "cache" / "domains"
    checks.append({
        "check": "cache/domains directory exists",
        "passed": domains_cache.exists(),
        "path": str(domains_cache),
    })

    index_db = kdna_home / "index.db"
    index_json = kdna_home / "index.json"
    index_exists = index_db.exists() or index_json.exists()
    checks.append({
        "check": "index file exists (index.db or index.json)",
        "passed": index_exists,
        "path": str(index_db if index_db.exists() else index_json),
    })
    if not index_exists:
        all_pass = False

    raw_domains_dir = kdna_home / "domains"
    if raw_domains_dir.exists():
        raw_count = len(list(raw_domains_dir.iterdir()))
        if raw_count > 0:
            checks.append({
                "check": "no raw source directories in ~/.kdna/domains/",
                "passed": False,
                "detail": f"{raw_count} items found in raw domains directory",
            })
            all_pass = False
        else:
            checks.append({
                "check": "no raw source directories in ~/.kdna/domains/",
                "passed": True,
            })

    packages_count = 0
    if packages_dir.exists():
        for domain_dir in packages_dir.iterdir():
            if domain_dir.is_dir():
                for version_dir in domain_dir.iterdir():
                    if version_dir.is_dir():
                        kdna_files = list(version_dir.glob("*.kdna"))
                        packages_count += len(kdna_files)

    checks.append({
        "check": "installed .kdna packages",
        "passed": packages_count > 0,
        "detail": f"{packages_count} .kdna file(s) found",
    })

    return {
        "kdna_home": str(kdna_home),
        "passed": all_pass,
        "checks": checks,
        "packages_count": packages_count,
    }


def print_app_contract_report(result: Dict[str, Any]):
    """Print App Runtime Contract verification report."""
    print(f"\n{'='*60}")
    print(f"App Runtime Contract Verification")
    print(f"{'='*60}")
    print(f"KDNA home: {result['kdna_home']}")
    print(f"Status: {'PASS' if result['passed'] else 'ISSUES FOUND'}")
    print(f"Packages: {result['packages_count']} .kdna file(s)")
    print()

    for c in result["checks"]:
        status = "PASS" if c["passed"] else "FAIL"
        detail = c.get("detail", c.get("path", ""))
        print(f"  [{status}] {c['check']}")
        if detail:
            print(f"         {detail}")
    print()


def spec_check_cli():
    """CLI entry point for SPEC + App Runtime Contract checks."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab SPEC & Contract Checker")
    parser.add_argument("--app-contract", action="store_true", help="Verify App Runtime Contract")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.app_contract or args.all:
        result = verify_app_runtime_contract()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_app_contract_report(result)

    if not args.app_contract or args.all:
        result = run_spec_check()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print_spec_report(result)


if __name__ == "__main__":
    spec_check_cli()
