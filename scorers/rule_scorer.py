#!/usr/bin/env python3
"""
KDNA Lab — Rule Scorer (L1 Hard Checks)

Reads run outputs + case definitions, applies machine-enforceable checks,
and produces structured scores.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

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
    if "json" in case.get("category", "") or "json" in " ".join(case.get("tags", [])):
        jv_passed, jv_detail = check_json_valid(output_body)
        checks["json_valid"] = {"passed": jv_passed, "detail": jv_detail}
        if not jv_passed:
            passed = False

    # character_count (if applicable)
    if "x_post" in case.get("category", "") or "character" in case.get("category", ""):
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


def generate_report(scores, output_dir):
    report_lines = []
    report_lines.append("# L1 Rule Score Report")
    report_lines.append("")
    report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append("")

    total = len(scores)
    passed = sum(1 for s in scores if s["score"]["L1"]["passed"])
    failed = total - passed

    report_lines.append("| Metric | Value |")
    report_lines.append("|--------|-------|")
    report_lines.append(f"| Total cases | {total} |")
    report_lines.append(f"| Passed | {passed} |")
    report_lines.append(f"| Failed | {failed} |")
    report_lines.append(f"| Pass rate | {passed/total*100:.0f}% |" if total > 0 else "| Pass rate | N/A |")
    report_lines.append("")

    if failed > 0:
        report_lines.append("## Failed Cases")
        report_lines.append("")
        for s in scores:
            if not s["score"]["L1"]["passed"]:
                checks = s["score"]["L1"]["checks"]
                report_lines.append(f"### {s['case_id']}")
                report_lines.append("")
                if "must_include" in checks:
                    missing = checks["must_include"].get("missing", [])
                    if missing:
                        report_lines.append(f"- **Missing required phrases:** {', '.join(missing)}")
                if "must_not_include" in checks:
                    violations = checks["must_not_include"].get("violations", [])
                    if violations:
                        report_lines.append(f"- **Banned phrases found:** {', '.join(violations)}")
                if "json_valid" in checks and not checks["json_valid"]["passed"]:
                    report_lines.append(f"- **JSON invalid:** {checks['json_valid']['detail']}")
                report_lines.append("")

    report_lines.append("## Detailed Scores")
    report_lines.append("")
    report_lines.append("| Case ID | Passed | Missing | Violations |")
    report_lines.append("|---------|--------|---------|------------|")
    for s in scores:
        checks = s["score"]["L1"]["checks"]
        missing = len(checks.get("must_include", {}).get("missing", []))
        violations = len(checks.get("must_not_include", {}).get("violations", []))
        status = "✅" if s["score"]["L1"]["passed"] else "❌"
        report_lines.append(f"| {s['case_id']} | {status} | {missing} | {violations} |")
    report_lines.append("")

    report_path = Path(output_dir) / f"l1_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))

    return str(report_path)


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
        report_path = generate_report(scores, report_dir)
        print(f"\n[INFO] Report → {report_path}")


if __name__ == "__main__":
    main()
