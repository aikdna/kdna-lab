#!/usr/bin/env python3
"""
KDNA Lab — Report Generator

Generates multi-format reports from scored experiment data.
Supports: domain_test, cli_regression, cross_model, summary, paper tables.

Input: scored results (JSON) or run index files.
Output: Markdown reports.
"""

import json
from pathlib import Path
from datetime import datetime

LAB_ROOT = Path(__file__).resolve().parent.parent

def load_data(input_file):
    with open(input_file) as f:
        return json.load(f)

def generate_domain_report(data, output_path):
    """Domain behavior test report."""
    results = data if isinstance(data, list) else data.get("results", [data])

    total = len(results)
    l1_passed = sum(1 for r in results if (
        r.get("score", {}).get("L1", {}).get("passed", False) or
        r.get("L1_pass", False)
    ))
    l2_results = [r for r in results if r.get("L2") or r.get("score", {}).get("L2")]

    lines = []
    lines.append("# Domain Test Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total cases | {total} |")
    lines.append(f"| L1 Passed | {l1_passed} |")
    lines.append(f"| L1 Pass Rate | {l1_passed/total*100:.0f}% |" if total > 0 else "")
    if l2_results:
        l2_passed = sum(1 for r in l2_results if r.get("score", {}).get("L2", {}).get("passed", False))
        lines.append(f"| L2 Passed | {l2_passed}/{len(l2_results)} |")
    lines.append("")

    l1_fails = [r for r in results if not (r.get("score", {}).get("L1", {}).get("passed", False) or r.get("L1_pass", False))]
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
    lines.append(f"| Case ID | L1 | L2 |")
    lines.append(f"|---------|-----|-----|")
    for r in results:
        cid = r.get("case_id") or r.get("id", "?")
        l1_passed = r.get("score", {}).get("L1", {}).get("passed") or r.get("L1_pass", False)
        l1 = "PASS" if l1_passed else "FAIL"
        l2_score = r.get("L2") or r.get("score", {}).get("L2", {})
        l2 = f"{l2_score.get('total', '?')}/{l2_score.get('max_total', '?')}" if l2_score and l2_score.get('total') is not None else "—"
        lines.append(f"| {cid} | {l1} | {l2} |")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path

def generate_cli_report(data, output_path):
    """CLI regression test report."""
    results = data if isinstance(data, list) else data.get("results", [data])

    total = len(results)
    passed = sum(1 for r in results if r.get("exit_code") == r.get("expected_exit_code", 0))

    lines = []
    lines.append("# CLI Regression Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total commands | {total} |")
    lines.append(f"| Passed | {passed} |")
    lines.append(f"| Failed | {total - passed} |")
    lines.append(f"| Pass rate | {passed/total*100:.0f}% |" if total > 0 else "")
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
    lines.append(f"| Case ID | Exit Code | Expected | Pass |")
    lines.append(f"|---------|-----------|----------|------|")
    for r in results:
        cid = r.get("case_id", "?")
        exit_code = r.get("exit_code", "?")
        expected = r.get("expected_exit_code", 0)
        status = "✅" if exit_code == expected else "❌"
        lines.append(f"| {cid} | {exit_code} | {expected} | {status} |")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path

def generate_paper_tables(data, output_path):
    """Generate paper-ready table data."""
    results = data if isinstance(data, list) else data.get("results", [data])

    # Simple CSV-style table
    lines = ["case_id,condition,L1_pass,must_include_missing,must_not_include_violations"]
    for r in results:
        cid = r.get("case_id", r.get("id", "?"))
        cond = r.get("condition", "kdna_full")
        l1 = r.get("score", {}).get("L1", {}).get("passed", r.get("L1_pass", False))
        mi = len(r.get("score", {}).get("L1", {}).get("checks", {}).get("must_include", {}).get("missing", []))
        mni = len(r.get("score", {}).get("L1", {}).get("checks", {}).get("must_not_include", {}).get("violations", []))
        lines.append(f"{cid},{cond},{l1},{mi},{mni}")

    csv_path = output_path.replace(".md", ".csv")
    with open(csv_path, "w") as f:
        f.write("\n".join(lines))

    # Markdown summary
    md_lines = []
    md_lines.append("# Paper Data Tables")
    md_lines.append("")
    md_lines.append(f"| Case | Condition | L1 | Missing | Violations |")
    md_lines.append(f"|------|-----------|-----|---------|------------|")
    for r in results:
        cid = r.get("case_id", r.get("id", "?"))
        cond = r.get("condition", "kdna_full")
        l1_passed = r.get("score", {}).get("L1", {}).get("passed") or r.get("L1_pass", False)
        l1 = "PASS" if l1_passed else "FAIL"
        mi = len(r.get("score", {}).get("L1", {}).get("checks", {}).get("must_include", {}).get("missing", []))
        mni = len(r.get("score", {}).get("L1", {}).get("checks", {}).get("must_not_include", {}).get("violations", []))
        md_lines.append(f"| {cid} | {cond} | {l1} | {mi} | {mni} |")
    md_lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(md_lines))

    return output_path, csv_path

def auto_detect_type(input_file):
    """Guess report type from data structure."""
    data = load_data(input_file)
    if isinstance(data, list) and data:
        sample = data[0]
        if "exit_code" in sample or "command" in sample:
            return "cli"
        if "model" in sample or "cross" in str(input_file).lower():
            return "cross_model"
        if "case_id" in sample:
            return "domain"
    return "domain"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Report Generator")
    parser.add_argument("input_file", nargs="?", help="Scored results file (JSON)")
    parser.add_argument("--type", choices=["domain", "cli", "cross_model", "summary", "paper"],
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
            print(f"\nUsage: python reports/generate_report.py <file> --type domain|cli|paper")
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
    elif report_type == "paper":
        path = args.output or str(output_dir / f"{base_name}_paper_tables.md")
        out, csv = generate_paper_tables(data, path)
        print(f"[INFO] CSV → {csv}")
    else:
        path = args.output or str(output_dir / f"{base_name}_summary.md")
        out = generate_domain_report(data, path)

    print(f"[INFO] Report → {out}")

if __name__ == "__main__":
    main()
