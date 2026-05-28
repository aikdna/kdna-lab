#!/usr/bin/env python3
"""
KDNA Lab — Report Generator

Generates multi-format reports from scored experiment data.
Supports: l1 (rule scorer), domain, cli, cross_model, paper tables.

Input: scored results (JSON/list).
Output: Markdown reports.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Union


LAB_ROOT = Path(__file__).resolve().parent.parent


def load_data(input_file: str) -> Any:
    with open(input_file) as f:
        return json.load(f)


# --- L1 Rule Score Report (used by rule_scorer.py) ---

def generate_l1_report(scores: List[Dict[str, Any]], output_dir: str) -> str:
    """Generate L1 rule-score report from in-memory scorer output."""
    lines: List[str] = []
    lines.append("# L1 Rule Score Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    total = len(scores)
    passed = sum(1 for s in scores if s["score"]["L1"]["passed"])
    failed = total - passed

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total cases | {total} |")
    lines.append(f"| Passed | {passed} |")
    lines.append(f"| Failed | {failed} |")
    lines.append(f"| Pass rate | {passed/total*100:.0f}% |" if total > 0 else "| Pass rate | N/A |")
    lines.append("")

    if failed > 0:
        lines.append("## Failed Cases")
        lines.append("")
        for s in scores:
            if not s["score"]["L1"]["passed"]:
                checks = s["score"]["L1"]["checks"]
                lines.append(f"### {s['case_id']}")
                lines.append("")
                if "must_include" in checks:
                    missing = checks["must_include"].get("missing", [])
                    if missing:
                        lines.append(f"- **Missing required phrases:** {', '.join(missing)}")
                if "must_not_include" in checks:
                    violations = checks["must_not_include"].get("violations", [])
                    if violations:
                        lines.append(f"- **Banned phrases found:** {', '.join(violations)}")
                if "json_valid" in checks and not checks["json_valid"]["passed"]:
                    lines.append(f"- **JSON invalid:** {checks['json_valid']['detail']}")
                if "character_count" in checks and not checks["character_count"]["passed"]:
                    cc = checks["character_count"]
                    lines.append(f"- **Character limit exceeded:** {cc['actual']}/{cc['max']}")
                lines.append("")

    lines.append("## Detailed Scores")
    lines.append("")
    lines.append("| Case ID | Passed | Missing | Violations |")
    lines.append("|---------|--------|---------|------------|")
    for s in scores:
        checks = s["score"]["L1"]["checks"]
        missing = len(checks.get("must_include", {}).get("missing", []))
        violations = len(checks.get("must_not_include", {}).get("violations", []))
        status = "PASS" if s["score"]["L1"]["passed"] else "FAIL"
        lines.append(f"| {s['case_id']} | {status} | {missing} | {violations} |")
    lines.append("")

    report_path = Path(output_dir) / f"l1_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    return str(report_path)


# --- Domain Report ---

def generate_domain_report(data: Union[List[Dict], Dict], output_path: str) -> str:
    """Domain behavior test report (L1 + optional L2)."""
    results = _normalize_list(data)

    total = len(results)
    l1_passed = sum(
        1 for r in results
        if r.get("score", {}).get("L1", {}).get("passed", False) or r.get("L1_pass", False)
    )
    l2_results = [r for r in results if r.get("L2") or r.get("score", {}).get("L2")]

    lines: List[str] = []
    lines.append("# Domain Test Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total cases | {total} |")
    lines.append(f"| L1 Passed | {l1_passed} |")
    if total > 0:
        lines.append(f"| L1 Pass Rate | {l1_passed/total*100:.0f}% |")
    if l2_results:
        l2_passed_val = sum(
            1 for r in l2_results
            if r.get("score", {}).get("L2", {}).get("passed", False)
        )
        lines.append(f"| L2 Passed | {l2_passed_val}/{len(l2_results)} |")
    lines.append("")

    l1_fails = [
        r for r in results
        if not (
            r.get("score", {}).get("L1", {}).get("passed", False)
            or r.get("L1_pass", False)
        )
    ]
    if l1_fails:
        lines.append("## L1 Failures")
        for r in l1_fails:
            cid = r.get("case_id", r.get("id", "?"))
            checks = r.get("score", {}).get("L1", {}).get("checks", {})
            lines.append(f"### {cid}")
            mi = checks.get("must_include", {})
            if mi.get("missing"):
                lines.append(f"- Missing: {mi['missing']}")
            mni = checks.get("must_not_include", {})
            if mni.get("violations"):
                lines.append(f"- Violations: {mni['violations']}")
            lines.append("")

    lines.append("## Detailed Scores")
    lines.append("| Case ID | L1 | L2 |")
    lines.append("|---------|-----|-----|")
    for r in results:
        cid = r.get("case_id") or r.get("id", "?")
        l1_ok = r.get("score", {}).get("L1", {}).get("passed") or r.get("L1_pass", False)
        l1 = "PASS" if l1_ok else "FAIL"
        l2_score = r.get("L2") or r.get("score", {}).get("L2", {})
        l2 = f"{l2_score.get('total', '?')}/{l2_score.get('max_total', '?')}" if l2_score and l2_score.get('total') is not None else "-"
        lines.append(f"| {cid} | {l1} | {l2} |")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path


# --- CLI Report ---

def generate_cli_report(data: Union[List[Dict], Dict], output_path: str) -> str:
    """CLI regression test report."""
    results = _normalize_list(data)
    total = len(results)
    passed = sum(1 for r in results if r.get("exit_code") == r.get("expected_exit_code", 0))

    lines: List[str] = []
    lines.append("# CLI Regression Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total commands | {total} |")
    lines.append(f"| Passed | {passed} |")
    lines.append(f"| Failed | {total - passed} |")
    if total > 0:
        lines.append(f"| Pass rate | {passed/total*100:.0f}% |")
    lines.append("")

    fails = [r for r in results if r.get("exit_code") != r.get("expected_exit_code", 0)]
    if fails:
        lines.append("## Failed Commands")
        for r in fails:
            lines.append(f"### {r.get('case_id', '?')}")
            lines.append(f"- Command: `{r.get('command', '?')}`")
            lines.append(f"- Expected exit: {r.get('expected_exit_code', 0)}, Got: {r.get('exit_code', '?')}")
            stderr = r.get("stderr", "")
            if stderr:
                lines.append(f"- stderr: `{stderr[:200]}`")
            lines.append("")

    lines.append("## All Results")
    lines.append("| Case ID | Exit Code | Expected | Pass |")
    lines.append("|---------|-----------|----------|------|")
    for r in results:
        cid = r.get("case_id", "?")
        exit_code = r.get("exit_code", "?")
        expected = r.get("expected_exit_code", 0)
        status = "PASS" if exit_code == expected else "FAIL"
        lines.append(f"| {cid} | {exit_code} | {expected} | {status} |")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path


# --- Cross-Model Report ---

def generate_cross_model_report(data: Union[List[Dict], Dict], output_path: str) -> str:
    """Cross-model consistency report."""
    results = _normalize_list(data)
    models = sorted(set(r.get("model", r.get("model_id", "?")) for r in results))
    total = len(results)

    lines: List[str] = []
    lines.append("# Cross-Model Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total results | {total} |")
    lines.append(f"| Models | {', '.join(models)} |")

    passed = sum(
        1 for r in results
        if r.get("L1_pass", r.get("score", {}).get("L1", {}).get("passed", False))
    )
    if total > 0:
        lines.append(f"| L1 Pass Rate | {passed/total*100:.0f}% |")
    lines.append("")

    lines.append("## Per-Model Results")
    lines.append("")
    for model_id in models:
        model_results = [r for r in results if r.get("model", r.get("model_id")) == model_id]
        if model_results:
            model_passed = sum(
                1 for r in model_results
                if r.get("L1_pass", r.get("score", {}).get("L1", {}).get("passed", False))
            )
            lines.append(f"- **{model_id}**: {model_passed}/{len(model_results)} passed")
    lines.append("")

    lines.append("## Detailed Results")
    lines.append("| Case | Model | L1 | Details |")
    lines.append("|------|-------|-----|---------|")
    for r in results:
        cid = r.get("case_id", "?")
        mid = r.get("model", r.get("model_id", "?"))
        l1_ok = r.get("L1_pass", r.get("score", {}).get("L1", {}).get("passed", False))
        l1 = "PASS" if l1_ok else "FAIL"
        details = ""
        if not l1_ok:
            parts = []
            if r.get("missing"):
                parts.append(f"miss:{len(r['missing'])}")
            if r.get("violations"):
                parts.append(f"viol:{len(r['violations'])}")
            details = ", ".join(parts)
        lines.append(f"| {cid} | {mid} | {l1} | {details} |")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path


# --- Paper Tables ---

def generate_paper_tables(data: Union[List[Dict], Dict], output_path: str) -> Tuple[str, str]:
    """Generate paper-ready table data (CSV + Markdown)."""
    results = _normalize_list(data)
    csv_lines = ["case_id,condition,L1_pass,must_include_missing,must_not_include_violations"]
    for r in results:
        cid = r.get("case_id", r.get("id", "?"))
        cond = r.get("condition", "kdna_full")
        l1 = r.get("score", {}).get("L1", {}).get("passed", r.get("L1_pass", False))
        mi = len(r.get("score", {}).get("L1", {}).get("checks", {})
                  .get("must_include", {}).get("missing", []))
        mni = len(r.get("score", {}).get("L1", {}).get("checks", {})
                   .get("must_not_include", {}).get("violations", []))
        csv_lines.append(f"{cid},{cond},{l1},{mi},{mni}")
    csv_path = output_path.replace(".md", ".csv")
    with open(csv_path, "w") as f:
        f.write("\n".join(csv_lines))

    md_lines: List[str] = []
    md_lines.append("# Paper Data Tables")
    md_lines.append("")
    md_lines.append("| Case | Condition | L1 | Missing | Violations |")
    md_lines.append("|------|-----------|-----|---------|------------|")
    for r in results:
        cid = r.get("case_id", r.get("id", "?"))
        cond = r.get("condition", "kdna_full")
        l1_ok = r.get("score", {}).get("L1", {}).get("passed") or r.get("L1_pass", False)
        l1 = "PASS" if l1_ok else "FAIL"
        mi = len(r.get("score", {}).get("L1", {}).get("checks", {})
                  .get("must_include", {}).get("missing", []))
        mni = len(r.get("score", {}).get("L1", {}).get("checks", {})
                   .get("must_not_include", {}).get("violations", []))
        md_lines.append(f"| {cid} | {cond} | {l1} | {mi} | {mni} |")
    md_lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(md_lines))
    return output_path, csv_path


# --- Helpers ---

def _normalize_list(data: Union[List, Dict]) -> List[Dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "results" in data:
            return data["results"]
        return [data]
    return []


def auto_detect_type(input_file: str) -> str:
    """Guess report type from data structure."""
    data = load_data(input_file)
    if isinstance(data, list) and data:
        sample = data[0]
        if "exit_code" in sample or "command" in sample:
            return "cli"
        if "model" in sample or "model_id" in sample:
            return "cross_model"
        if "case_id" in sample:
            return "domain"
    return "domain"


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Report Generator")
    parser.add_argument("input_file", nargs="?", help="Scored results file (JSON)")
    parser.add_argument("--type", choices=["domain", "cli", "cross_model", "paper"],
                        default=None, help="Report type (auto-detected if omitted)")
    parser.add_argument("--output", default=None, help="Output path")
    args = parser.parse_args()

    if not args.input_file:
        outputs_dir = LAB_ROOT / "outputs"
        candidates = list(outputs_dir.glob("*index*.json")) + list(outputs_dir.glob("*.json"))
        if candidates:
            print("[INFO] Available data files:")
            for c in sorted(candidates):
                print(f"  {c.name}")
            print()
            print("Usage: python reports/generate_report.py <file> --type domain|cli|cross_model|paper")
        else:
            print("[ERROR] No data files found in outputs/")
        return

    data = load_data(args.input_file)
    report_type = args.type or auto_detect_type(args.input_file)
    output_dir = Path(args.output).parent if args.output else LAB_ROOT / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(args.input_file).stem

    print(f"[INFO] Report type: {report_type}")

    if report_type == "domain":
        path = args.output or str(output_dir / f"{base_name}_domain_report.md")
        out = generate_domain_report(data, path)
    elif report_type == "cli":
        path = args.output or str(output_dir / f"{base_name}_cli_report.md")
        out = generate_cli_report(data, path)
    elif report_type == "cross_model":
        path = args.output or str(output_dir / f"{base_name}_cross_model_report.md")
        out = generate_cross_model_report(data, path)
    elif report_type == "paper":
        path = args.output or str(output_dir / f"{base_name}_paper_tables.md")
        out, csv = generate_paper_tables(data, path)
        print(f"[INFO] CSV -> {csv}")
    else:
        path = args.output or str(output_dir / f"{base_name}_summary.md")
        out = generate_domain_report(data, path)

    print(f"[INFO] Report -> {out}")


if __name__ == "__main__":
    main()
