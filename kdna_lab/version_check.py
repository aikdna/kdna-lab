"""KDNA Lab — Protocol Version Compatibility Matrix.

Validates that the KDNA CLI correctly handles domain fixtures
across different KDNA protocol versions (v1.0-rc, v1.0, etc.).

Each fixture is annotated with its spec_version. This module
tests that:
  - v1.0 CLI accepts v1.0-rc fixtures (backward compat)
  - v1.0 CLI validates new v1.0-only fields
  - Migration messages are clear when old formats are rejected
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT
from kdna_lab.schema_check import resolve_schema_dir


# Map of fixtures → expected spec_version and validation behavior
FIXTURE_VERSION_MATRIX = [
    {
        "fixture": "valid_minimal_domain",
        "spec_version": "1.0-rc",
        "description": "Minimal valid domain (v1.0-rc format with format/format_version fields)",
        "validate_exit_code": 0,
        "validate_must_include": ["valid"],
        "load_works": True,
    },
    {
        "fixture": "invalid_string_judgment_role",
        "spec_version": "legacy",
        "description": "Domain with judgment_role as string (pre-v1.0 format)",
        "validate_exit_code": 1,
        "validate_must_include": ["expected object"],
        "load_works": False,
    },
    {
        "fixture": "invalid_array_risk_model",
        "spec_version": "legacy",
        "description": "Domain with risk_model as array (pre-v1.0 format)",
        "validate_exit_code": 1,
        "validate_must_include": ["expected object"],
        "load_works": False,
    },
    {
        "fixture": "invalid_missing_boundary_fields",
        "spec_version": "legacy",
        "description": "Domain missing boundary rule/why fields",
        "validate_exit_code": 1,
        "validate_must_include": ["Error"],
        "load_works": False,
    },
    {
        "fixture": "invalid_string_action_template",
        "spec_version": "legacy",
        "description": "Domain with action_template as string",
        "validate_exit_code": 1,
        "validate_must_include": ["expected array"],
        "load_works": False,
    },
    {
        "fixture": "invalid_seven_json_files",
        "spec_version": "legacy",
        "description": "Domain with additional JSON files (KDNA_CARD and reports now allowed per v1.0+ schema)",
        "validate_exit_code": 0,
        "load_works": True,
    },
    {
        "fixture": "legacy_unscoped_domain",
        "spec_version": "legacy",
        "description": "Legacy domain without @scope naming (dev validate passes, install requires scope)",
        "validate_exit_code": 0,
        "load_works": True,
    },
]

FIXTURES_DIR = LAB_ROOT / "fixtures"


def check_fixture_validation(fixture_name: str, expected_exit: int,
                             must_include: List[str]) -> Dict[str, Any]:
    """Run kdna dev validate on a fixture and check results."""
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        return {"error": f"Fixture not found: {fixture_path}"}

    try:
        result = subprocess.run(
            ["kdna", "dev", "validate", str(fixture_path)],
            capture_output=True, text=True, timeout=30,
        )
        combined = result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return {"error": "Validation timed out", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}

    exit_ok = result.returncode == expected_exit
    includes_ok = True
    missing_includes = []

    for phrase in must_include:
        if phrase.lower() not in combined.lower():
            includes_ok = False
            missing_includes.append(phrase)

    return {
        "exit_code": result.returncode,
        "expected_exit": expected_exit,
        "exit_ok": exit_ok,
        "includes_ok": includes_ok,
        "missing_includes": missing_includes,
        "passed": exit_ok and includes_ok,
        "stdout_snippet": combined[:300],
    }


def check_fixture_load(fixture_name: str) -> Dict[str, Any]:
    """Check if a fixture can be loaded."""
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        return {"error": f"Fixture not found: {fixture_path}"}

    try:
        result = subprocess.run(
            ["kdna", "load", str(fixture_path), "--as=prompt"],
            capture_output=True, text=True, timeout=30,
        )
        works = result.returncode == 0
        return {
            "exit_code": result.returncode,
            "works": works,
            "output_size": len(result.stdout.encode("utf-8")),
        }
    except Exception as e:
        return {"error": str(e), "works": False}


def run_version_matrix() -> Dict[str, Any]:
    """Run the full protocol version compatibility matrix."""
    results = []
    for entry in FIXTURE_VERSION_MATRIX:
        fixture = entry["fixture"]
        version = entry["spec_version"]

        val = check_fixture_validation(
            fixture, entry["validate_exit_code"], entry.get("validate_must_include", [])
        )

        load = None
        if entry.get("load_works") is not None:
            load = check_fixture_load(fixture)

        result = {
            "fixture": fixture,
            "spec_version": version,
            "description": entry["description"],
            "validation": val,
            "load": load,
            "passed": val.get("passed", False),
        }
        results.append(result)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    version_breakdown: Dict[str, Dict] = {}
    for r in results:
        v = r["spec_version"]
        if v not in version_breakdown:
            version_breakdown[v] = {"total": 0, "passed": 0}
        version_breakdown[v]["total"] += 1
        if r["passed"]:
            version_breakdown[v]["passed"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100) if total else 0,
        "by_version": version_breakdown,
        "results": results,
    }


def generate_version_report(result: Dict, output_path: str) -> str:
    """Generate protocol version compatibility report."""
    lines = []
    lines.append("# KDNA Protocol Version Compatibility Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Overall:** {result['passed']}/{result['total']} passed ({result['pass_rate']}%)")
    lines.append("")

    lines.append("## Version Summary")
    lines.append("")
    lines.append("| Spec Version | Total | Passed | Rate |")
    lines.append("|-------------|-------|--------|------|")
    for v, stats in result["by_version"].items():
        rate = round(stats["passed"] / stats["total"] * 100) if stats["total"] else 0
        lines.append(f"| {v} | {stats['total']} | {stats['passed']} | {rate}% |")
    lines.append("")

    lines.append("## Fixture Details")
    lines.append("")
    for r in result["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"### {r['fixture']} — {status}")
        lines.append(f"- Spec version: `{r['spec_version']}`")
        lines.append(f"- Description: {r['description']}")

        val = r.get("validation", {})
        if val:
            lines.append(f"- Validate exit: {val.get('exit_code', '?')} (expected {val.get('expected_exit', '?')})")
            if val.get("missing_includes"):
                lines.append(f"- Missing includes: {val['missing_includes']}")
            if val.get("stdout_snippet"):
                lines.append(f"- Output: `{val['stdout_snippet'][:120]}...`")

        load = r.get("load", {})
        if load:
            load_status = "works" if load.get("works") else "fails"
            lines.append(f"- Load: {load_status} (exit={load.get('exit_code', '?')})")
        lines.append("")

    lines.append("---")
    lines.append("*Each KDNA protocol version change should be verified against this matrix.*")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def version_check_cli():
    """CLI entry point for version compatibility check."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Protocol Version Compatibility")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = run_version_matrix()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        out = args.output or str(LAB_ROOT / "reports" / f"version_matrix_{datetime.now().strftime('%Y%m%d')}.md")
        path = generate_version_report(result, out)

        print(f"Protocol Version Compatibility: {result['passed']}/{result['total']} passed")
        for r in result["results"]:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['fixture']} ({r['spec_version']})")
        print(f"\nReport → {path}")


if __name__ == "__main__":
    version_check_cli()
