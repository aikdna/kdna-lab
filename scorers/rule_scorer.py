#!/usr/bin/env python3
"""
KDNA Lab — Rule Scorer (L1 Hard Checks)

Reads run outputs + case definitions, applies machine-enforceable checks,
and produces structured scores.
"""

import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_ROOT))

from lib.cases import load_cases
from lib.outputs import find_outputs, extract_output_body
from lib.checks import (
    check_must_include,
    check_must_not_include,
    check_json_valid,
    check_character_count,
)
from reports.generate_report import generate_l1_report


def _area_or_category(case: dict) -> str:
    return case.get("area", "") or case.get("category", "")


def _should_check_json(case: dict) -> bool:
    tags_str = _area_or_category(case) + " " + " ".join(case.get("tags", []))
    return "json" in tags_str.lower()


def _should_check_char_count(case: dict) -> bool:
    tags_str = _area_or_category(case)
    return "x_post" in tags_str or "character" in tags_str


def score_case(case, output_body):
    checks = {}
    passed = True

    # must_include
    mi_passed, mi_results = check_must_include(output_body, case.get("must_include", []))
    checks["must_include"] = {
        "passed": mi_passed,
        "missing": [r["item"] for r in mi_results if not r["found"]],
        "details": mi_results
    }
    if not mi_passed:
        passed = False

    # must_not_include
    mni_passed, mni_violations = check_must_not_include(output_body, case.get("must_not_include", []))
    checks["must_not_include"] = {
        "passed": mni_passed,
        "violations": mni_violations
    }
    if not mni_passed:
        passed = False

    # json_valid (if applicable)
    if _should_check_json(case):
        jv_passed, jv_detail = check_json_valid(output_body)
        checks["json_valid"] = {"passed": jv_passed, "detail": jv_detail}
        if not jv_passed:
            passed = False

    # character_count (if applicable)
    if _should_check_char_count(case):
        max_chars = 280
        cc_passed, cc_actual, cc_max = check_character_count(output_body, max_chars)
        checks["character_count"] = {"passed": cc_passed, "actual": cc_actual, "max": cc_max}
        if not cc_passed:
            passed = False

    return {
        "L1": {
            "passed": passed,
            "checks": checks
        }
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Rule Scorer")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--output-dir", default=None, help="Directory containing raw outputs")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--json", action="store_true", help="Output scores as JSON")
    args = parser.parse_args()

    case_file = args.case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    output_dir = args.output_dir or str(LAB_ROOT / "outputs")
    report_dir = str(LAB_ROOT / "reports")
    log = sys.stderr if args.json else sys.stdout

    cases = load_cases(case_file)
    print(f"[INFO] Loaded {len(cases)} case definitions", file=log)

    outputs = find_outputs(output_dir)
    print(f"[INFO] Found {len(outputs)} output file(s)", file=log)

    scores = []
    for case_id, case in cases.items():
        if case_id in outputs:
            for output_info in outputs[case_id]:
                body = extract_output_body(output_info["content"])
                score = score_case(case, body)
                scores.append({
                    "case_id": case_id,
                    "output_file": output_info["file"],
                    "score": score,
                    "case": case
                })
                status = "PASS" if score["L1"]["passed"] else "FAIL"
                print(f"[{status}] {case_id}", file=log)

    if not scores:
        print("[WARN] No matched outputs found. Run the runner first, then point scorer to the output directory.", file=log)
        return

    if args.json:
        print(json.dumps([{
            "case_id": s["case_id"],
            "L1_passed": s["score"]["L1"]["passed"],
            "checks": s["score"]["L1"]["checks"]
        } for s in scores], indent=2, ensure_ascii=False))
    else:
        report_path = generate_l1_report(scores, report_dir)
        print(f"\n[INFO] Report → {report_path}")


if __name__ == "__main__":
    main()
