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

def load_cases(case_file):
    cases = {}
    with open(case_file) as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                cases[c["id"]] = c
    return cases

def find_outputs(output_dir):
    outputs = {}
    raw_dir = Path(output_dir) / "raw"
    if not raw_dir.exists():
        return outputs

    # Domain outputs: *.txt files with # Case: header
    for f in raw_dir.glob("*.txt"):
        if "_prompt" in f.stem:
            continue  # skip prompt-only files
        content = f.read_text()
        lines = content.split("\n")
        case_id = f.stem
        for line in lines[:15]:
            if line.startswith("# Case:"):
                case_id = line.replace("# Case:", "").strip()
                break
        key = case_id
        if key not in outputs:
            outputs[key] = []
        outputs[key].append({"file": str(f), "case_id": case_id, "content": content, "type": "domain"})

    # CLI outputs: *.json files with exit_code/stdout/stderr
    for f in raw_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        # Check if it looks like a CLI result (has exit_code)
        if isinstance(data, dict) and "exit_code" in data and "stdout" in data:
            case_id = data.get("case_id", f.stem)
            # Combine stdout+stderr for must_include/must_not_include checks
            combined = (data.get("stdout", "") + "\n" + data.get("stderr", ""))
            key = case_id
            if key not in outputs:
                outputs[key] = []
            outputs[key].append({"file": str(f), "case_id": case_id, "content": combined, "type": "cli"})
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "exit_code" in item:
                    cid = item.get("case_id", f.stem)
                    combined = (item.get("stdout", "") + "\n" + item.get("stderr", ""))
                    key = cid
                    if key not in outputs:
                        outputs[key] = []
                    outputs[key].append({"file": str(f), "case_id": cid, "content": combined, "type": "cli"})

    return outputs

def extract_output_body(content):
    """Extract the actual response from the marked-up output file."""
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        body = content  # fallback
    return body

def check_must_include(output, must_include):
    results = []
    all_passed = True
    for item in must_include:
        found = item.lower() in output.lower()
        results.append({"item": item, "found": found})
        if not found:
            all_passed = False
    return all_passed, results

NEGATION_PATTERNS = [
    "不是", "并非", "而非", "而不是", "不算是", "不能算", "不等于",
    "not ", "is not ", "are not ", "isn't ", "aren't ", "rather than",
    "不是...而是", "不是...是"
]

def _is_in_negation_context(text, term, window=40):
    text_lower = text.lower()
    term_lower = term.lower()
    idx = text_lower.find(term_lower)
    if idx == -1:
        return False
    context = text_lower[max(0, idx-window):idx]
    for pat in NEGATION_PATTERNS:
        if pat in context:
            return True
    return False

def check_must_not_include(output, must_not_include):
    violations = []
    all_clean = True
    output_lower = output.lower()
    for item in must_not_include:
        if item.lower() in output_lower:
            if _is_in_negation_context(output, item):
                continue  # negated usage is allowed
            violations.append(item)
            all_clean = False
    return all_clean, violations

def check_json_valid(output):
    # Try to extract JSON block from output
    import re
    json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
    if json_match:
        try:
            json.loads(json_match.group(1))
            return True, "valid (code block)"
        except json.JSONDecodeError as e:
            return False, f"invalid JSON in code block: {e}"
    # Try raw
    if output.strip().startswith("{"):
        try:
            json.loads(output.strip())
            return True, "valid (raw)"
        except json.JSONDecodeError:
            pass
    return False, "no JSON found in output (JSON was required)"

def check_character_count(output, max_chars=None):
    actual = len(output)
    if max_chars and actual > max_chars:
        return False, actual, max_chars
    return True, actual, max_chars

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
    report_lines.append(f"# L1 Rule Score Report")
    report_lines.append(f"")
    report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append(f"")
    report_lines.append(f"## Summary")
    report_lines.append(f"")

    total = len(scores)
    passed = sum(1 for s in scores if s["score"]["L1"]["passed"])
    failed = total - passed

    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    report_lines.append(f"| Total cases | {total} |")
    report_lines.append(f"| Passed | {passed} |")
    report_lines.append(f"| Failed | {failed} |")
    report_lines.append(f"| Pass rate | {passed/total*100:.0f}% |" if total > 0 else "| Pass rate | N/A |")
    report_lines.append(f"")

    if failed > 0:
        report_lines.append(f"## Failed Cases")
        report_lines.append(f"")
        for s in scores:
            if not s["score"]["L1"]["passed"]:
                checks = s["score"]["L1"]["checks"]
                report_lines.append(f"### {s['case_id']}")
                report_lines.append(f"")
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
                report_lines.append(f"")

    report_lines.append(f"## Detailed Scores")
    report_lines.append(f"")
    report_lines.append(f"| Case ID | Passed | Missing | Violations |")
    report_lines.append(f"|---------|--------|---------|------------|")
    for s in scores:
        checks = s["score"]["L1"]["checks"]
        missing = len(checks.get("must_include", {}).get("missing", []))
        violations = len(checks.get("must_not_include", {}).get("violations", []))
        status = "✅" if s["score"]["L1"]["passed"] else "❌"
        report_lines.append(f"| {s['case_id']} | {status} | {missing} | {violations} |")
    report_lines.append(f"")

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
