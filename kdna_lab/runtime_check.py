"""KDNA Lab — Runtime Pipeline Checker.

Validates the complete KDNA runtime pipeline:
  route → match → select → load → postvalidate

Tests that the runtime control plane correctly identifies tasks,
routes to appropriate domains, selects loading strategies, and
validates post-generation outputs.

This covers the "algorithm layer" of KDNA — the 5-gate 7-state
routing, signal matching, and selection policies.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner


# ---- Route Test Cases ----

ROUTE_TEST_CASES = [
    {
        "id": "route_writing_diagnosis",
        "input": "请帮我诊断这篇文章有什么结构性问题",
        "expected": {
            "needs_kdna": True,
            "status_not": "ERROR",
            "has_trace_id": True,
        },
        "desc": "Writing diagnosis → should detect judgment need",
    },
    {
        "id": "route_creative_writing",
        "input": "帮我写一篇关于爱情的散文",
        "expected": {
            "needs_kdna": False,
            "status_not": "LOAD",
        },
        "desc": "Creative writing → should skip (no judgment needed)",
    },
    {
        "id": "route_code_review_uninstalled",
        "input": "请帮我审查这段代码的安全性",
        "expected": {
            "status": "SKIP_NO_LOCAL_DOMAIN",
            "action": "skip",
        },
        "desc": "Code review without installed domain → skip",
    },
    {
        "id": "route_empty_input",
        "input": "",
        "expected": {
            "status_not": "LOAD",
        },
        "desc": "Empty input → should not load",
    },
    {
        "id": "route_json_output",
        "input": "请帮我诊断这篇文章有什么结构性问题",
        "expected": {
            "json_parsable": True,
            "has_fields": ["status", "action", "needs_kdna", "trace_id"],
        },
        "desc": "JSON output should contain required fields",
    },
]

# ---- Match Test Cases ----

MATCH_TEST_CASES = [
    {
        "id": "match_writing_signal",
        "input": "请帮我诊断这篇文章有什么结构性问题",
        "expected": {
            "json_parsable": True,
            "has_fields": ["task", "dropped"],
        },
        "desc": "Match for writing task → returns match signals",
    },
    {
        "id": "match_no_signal",
        "input": "今天天气怎么样",
        "expected": {
            "json_parsable": True,
            "has_no_matches": True,
        },
        "desc": "Irrelevant query → no strong matches",
    },
]

# ---- Select Test Cases ----

SELECT_TEST_CASES = [
    {
        "id": "select_writing",
        "input": "请帮我诊断这篇文章有什么结构性问题",
        "expected": {
            "json_parsable": True,
            "has_fields": ["input", "selected", "max_domains"],
        },
        "desc": "Select for writing → returns selection",
    },
]

# ---- Load Profile Test Cases ----

LOAD_PROFILE_CASES = [
    {"id": "load_profile_index", "profile": "index", "min_size": 500, "max_size": 10000},
    {"id": "load_profile_compact", "profile": "compact", "min_size": 2000, "max_size": 15000},
    {"id": "load_profile_scenario", "profile": "scenario", "min_size": 1000, "max_size": 15000},
    {"id": "load_profile_full", "profile": "full", "min_size": 3000, "max_size": 20000},
]

# ---- Postvalidate Test Cases ----

POSTVALIDATE_TEST_CASES = [
    {
        "id": "postvalidate_no_file",
        "input": "kdna postvalidate @aikdna/writing --output /tmp/nonexistent_kdna_lab_test_output.txt",
        "expected_exit_not_zero": True,
        "desc": "Postvalidate without output file should fail",
    },
]


def run_json_command(command: str) -> Optional[Dict]:
    """Run a kdna command with --json and parse the output."""
    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, timeout=30,
        )
        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        pass
    return None


def run_text_command(command: str) -> Optional[str]:
    """Run a kdna command and return text output."""
    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return None


def check_route_cases(domain: str = "@aikdna/writing") -> List[Dict]:
    """Run all route test cases."""
    results = []
    for tc in ROUTE_TEST_CASES:
        output = run_json_command(f'kdna route "{tc["input"]}" --json')

        entry = {"case_id": tc["id"], "desc": tc["desc"], "passed": True, "errors": []}

        if output is None:
            entry["passed"] = False
            entry["errors"].append("No JSON output")
            results.append(entry)
            continue

        for key, expected in tc["expected"].items():
            if key == "json_parsable":
                continue  # Already verified
            elif key == "status":
                if output.get("status") != expected:
                    entry["passed"] = False
                    entry["errors"].append(f"status: expected {expected}, got {output.get('status')}")
            elif key == "status_not":
                if output.get("status") == expected:
                    entry["passed"] = False
                    entry["errors"].append(f"status should not be {expected}")
            elif key == "has_trace_id":
                if not output.get("trace_id"):
                    entry["passed"] = False
                    entry["errors"].append("Missing trace_id")
            elif key == "has_fields":
                for field in expected:
                    if field not in output:
                        entry["passed"] = False
                        entry["errors"].append(f"Missing field: {field}")
            elif key == "needs_kdna":
                if output.get("needs_kdna") != expected:
                    entry["passed"] = False
                    entry["errors"].append(f"needs_kdna: expected {expected}")
            elif key == "action":
                if output.get("action") != expected:
                    entry["passed"] = False
                    entry["errors"].append(f"action: expected {expected}")

        entry["output_summary"] = {
            "status": output.get("status"),
            "action": output.get("action"),
            "confidence": output.get("confidence"),
        }
        results.append(entry)

    return results


def check_match_cases() -> List[Dict]:
    """Run all match test cases."""
    results = []
    for tc in MATCH_TEST_CASES:
        output = run_json_command(f'kdna match "{tc["input"]}" --json')

        entry = {"case_id": tc["id"], "desc": tc["desc"], "passed": True, "errors": []}

        if output is None:
            entry["passed"] = False
            entry["errors"].append("No JSON output")
            results.append(entry)
            continue

        for key, expected in tc["expected"].items():
            if key == "json_parsable":
                continue
            elif key == "has_fields":
                for field in expected:
                    if field not in output:
                        entry["passed"] = False
                        entry["errors"].append(f"Missing field: {field}")
            elif key == "has_no_matches":
                has_matches = bool(output.get("hints")) or not output.get("no_strong_matches", True)
                if has_matches:
                    entry["passed"] = False
                    entry["errors"].append("Expected no matches")

        results.append(entry)
    return results


def check_select_cases() -> List[Dict]:
    """Run all select test cases."""
    results = []
    for tc in SELECT_TEST_CASES:
        output = run_json_command(f'kdna select --input "{tc["input"]}" --json')

        entry = {"case_id": tc["id"], "desc": tc["desc"], "passed": True, "errors": []}

        if output is None:
            entry["passed"] = False
            entry["errors"].append("No JSON output")
            results.append(entry)
            continue

        for key, expected in tc["expected"].items():
            if key == "json_parsable":
                continue
            elif key == "has_fields":
                for field in expected:
                    if field not in output:
                        entry["passed"] = False
                        entry["errors"].append(f"Missing field: {field}")

        results.append(entry)
    return results


def check_load_profiles(domain: str = "@aikdna/writing") -> List[Dict]:
    """Compare load profile outputs."""
    results = []
    for tc in LOAD_PROFILE_CASES:
        output = run_text_command(f"kdna load {domain} --profile={tc['profile']}")

        entry = {"case_id": tc["id"], "desc": f"Load {domain} with {tc['profile']} profile",
                 "passed": True, "errors": []}

        if output is None:
            entry["passed"] = False
            entry["errors"].append("Command failed")
            entry["size"] = 0
        else:
            size = len(output.encode("utf-8"))
            entry["size"] = size
            if size < tc["min_size"]:
                entry["passed"] = False
                entry["errors"].append(f"Size {size} < min {tc['min_size']} (profile may be empty)")
            if size > tc["max_size"]:
                entry["errors"].append(f"Size {size} > max {tc['max_size']} (unusually large)")

        results.append(entry)
    return results


def check_postvalidate_cases() -> List[Dict]:
    """Run postvalidate test cases."""
    results = []
    for tc in POSTVALIDATE_TEST_CASES:
        try:
            result = subprocess.run(
                tc["input"].split(), capture_output=True, text=True, timeout=30,
            )
            exit_code = result.returncode
        except Exception:
            exit_code = -1

        entry = {"case_id": tc["id"], "desc": tc["desc"], "passed": True, "errors": [], "exit_code": exit_code}

        if tc.get("expected_exit_not_zero") and exit_code == 0:
            entry["passed"] = False
            entry["errors"].append(f"Expected non-zero exit, got {exit_code}")

        results.append(entry)
    return results


def run_runtime_checks(domain: str = "@aikdna/writing") -> Dict[str, Any]:
    """Run all runtime pipeline checks."""
    route_results = check_route_cases(domain)
    match_results = check_match_cases()
    select_results = check_select_cases()
    profile_results = check_load_profiles(domain)
    postvalidate_results = check_postvalidate_cases()

    all_results = route_results + match_results + select_results + profile_results + postvalidate_results
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100) if total else 0,
        "route": route_results,
        "match": match_results,
        "select": select_results,
        "profiles": profile_results,
        "postvalidate": postvalidate_results,
    }


def print_runtime_report(result: Dict[str, Any]):
    """Print human-readable runtime pipeline report."""
    print(f"\n{'='*60}")
    print(f"KDNA Runtime Pipeline Report")
    print(f"{'='*60}")
    print(f"Overall: {result['passed']}/{result['total']} passed ({result['pass_rate']}%)")
    print()

    sections = [
        ("Route (5-Gate 7-State)", result["route"]),
        ("Match (Signal Matching)", result["match"]),
        ("Select (Selection Policy)", result["select"]),
        ("Load Profiles", result["profiles"]),
        ("Postvalidate", result["postvalidate"]),
    ]

    for label, items in sections:
        print(f"--- {label} ---")
        for item in items:
            status = "PASS" if item["passed"] else "FAIL"
            print(f"  [{status}] {item['case_id']}: {item['desc']}")
            if item.get("size"):
                print(f"          Size: {item['size']} bytes")
            if item.get("errors"):
                for e in item["errors"]:
                    print(f"          Error: {e}")
            if item.get("output_summary"):
                s = item["output_summary"]
                print(f"          status={s.get('status')}, action={s.get('action')}, conf={s.get('confidence')}")
        print()

    # Profile comparison table
    profiles = result.get("profiles", [])
    if profiles:
        print("--- Load Profile Comparison ---")
        print(f"  {'Profile':<12} {'Size (bytes)':>12}")
        for p in profiles:
            print(f"  {p['case_id'].replace('load_profile_', ''):<12} {p.get('size', 0):>12,}")
        print()


def runtime_check_cli():
    """CLI entry point for runtime pipeline checks."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Runtime Pipeline Checker")
    parser.add_argument("--domain", default="@aikdna/writing", help="Domain to test")
    parser.add_argument("--route-only", action="store_true")
    parser.add_argument("--profiles-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.route_only:
        results = check_route_cases(args.domain)
        result = {"route": results}
    elif args.profiles_only:
        results = check_load_profiles(args.domain)
        result = {"profiles": results}
    else:
        result = run_runtime_checks(args.domain)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if "route" in result:
            print_runtime_report(result)
        else:
            for r in result.get("route", result.get("profiles", [])):
                status = "PASS" if r["passed"] else "FAIL"
                print(f"[{status}] {r['case_id']}: {r['desc']}")


if __name__ == "__main__":
    runtime_check_cli()
