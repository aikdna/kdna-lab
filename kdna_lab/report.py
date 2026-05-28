"""KDNA Lab — Report Generator.

Generates multi-format reports from scored experiment data.
Supports: l1 (rule scorer), domain, cli, cross_model, paper tables.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Union


def _normalize_list(data: Union[List, Dict]) -> List[Dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "results" in data:
            return data["results"]
        return [data]
    return []


def generate_l1_report(scores: List[Dict[str, Any]], output_dir: str) -> str:
    """Generate L1 rule-score report from scored results."""
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
    report_path.write_text("\n".join(lines))
    return str(report_path)


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

    Path(output_path).write_text("\n".join(lines))
    return output_path


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

    Path(output_path).write_text("\n".join(lines))
    return output_path


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

    Path(output_path).write_text("\n".join(lines))
    return output_path


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
    Path(csv_path).write_text("\n".join(csv_lines))

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

    Path(output_path).write_text("\n".join(md_lines))
    return output_path, csv_path


def auto_detect_type(input_file: str) -> str:
    """Guess report type from data structure."""
    data = json.loads(Path(input_file).read_text())
    if isinstance(data, list) and data:
        sample = data[0]
        if "exit_code" in sample or "command" in sample:
            return "cli"
        if "model" in sample or "model_id" in sample:
            return "cross_model"
        if "case_id" in sample:
            return "domain"
    return "domain"


# --- Multi-Condition Comparison Report (No KDNA / Best Prompt / KDNA) ---

def generate_comparison_report(data: Union[List[Dict], Dict], output_path: str) -> str:
    """Generate a multi-condition comparison report.

    Groups results by case_id, then compares outcomes across conditions
    (no_kdna, best_prompt, kdna_full, etc.). This is the primary report
    for proving KDNA improves judgment behavior beyond strong prompting.
    """
    results = _normalize_list(data)

    cases: Dict[str, Dict[str, Dict]] = {}
    conditions_order = []

    for r in results:
        cid = r.get("case_id", r.get("id", "?"))
        cond = r.get("condition", "unknown")
        if cond not in conditions_order:
            conditions_order.append(cond)

        l1_ok = _is_passing(r)
        missing = len(r.get("missing", [])) or len(
            r.get("score", {}).get("L1", {}).get("checks", {}).get("must_include", {}).get("missing", [])
        )
        violations = len(r.get("violations", [])) or len(
            r.get("score", {}).get("L1", {}).get("checks", {}).get("must_not_include", {}).get("violations", [])
        )

        if cid not in cases:
            cases[cid] = {}
        cases[cid][cond] = {
            "passed": l1_ok,
            "missing": missing,
            "violations": violations,
        }

    lines: List[str] = []
    lines.append("# Multi-Condition Comparison Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Conditions")
    lines.append("")
    for cond in conditions_order:
        label = _condition_label(cond)
        lines.append(f"- **{cond}**: {label}")
    lines.append("")

    # Aggregate stats per condition
    lines.append("## Aggregate Results")
    lines.append("")
    lines.append("| Condition | Passed | Failed | Pass Rate | Avg Missing | Avg Violations |")
    lines.append("|-----------|--------|--------|-----------|-------------|----------------|")
    for cond in conditions_order:
        cond_results = [cases[cid].get(cond) for cid in cases if cond in cases[cid]]
        if not cond_results:
            continue
        passed = sum(1 for r in cond_results if r["passed"])
        failed = len(cond_results) - passed
        rate = passed / len(cond_results) * 100 if cond_results else 0
        avg_m = sum(r["missing"] for r in cond_results) / len(cond_results)
        avg_v = sum(r["violations"] for r in cond_results) / len(cond_results)
        lines.append(f"| {_condition_label(cond)} | {passed} | {failed} | {rate:.0f}% | {avg_m:.1f} | {avg_v:.1f} |")
    lines.append("")

    # Pairwise deltas against no_kdna
    baseline = "no_kdna" if "no_kdna" in conditions_order else conditions_order[0]
    lines.append(f"## Improvement vs {_condition_label(baseline)}")
    lines.append("")
    lines.append("| Condition | Δ Pass Rate | Δ Missing | Δ Violations |")
    lines.append("|-----------|------------|-----------|-------------|")
    for cond in conditions_order:
        if cond == baseline:
            continue
        bl_results = [cases[cid].get(baseline) for cid in cases if baseline in cases[cid]]
        c_results = [cases[cid].get(cond) for cid in cases if cond in cases[cid]]
        if not bl_results or not c_results:
            continue
        bl_pass = sum(1 for r in bl_results if r["passed"])
        c_pass = sum(1 for r in c_results if r["passed"])
        delta = c_pass - bl_pass
        bl_m = sum(r["missing"] for r in bl_results)
        c_m = sum(r["missing"] for r in c_results)
        bl_v = sum(r["violations"] for r in bl_results)
        c_v = sum(r["violations"] for r in c_results)
        lines.append(f"| {_condition_label(cond)} | {delta:+d} | {c_m - bl_m:+d} | {c_v - bl_v:+d} |")
    lines.append("")

    # Per-case matrix
    lines.append("## Case-by-Case Matrix")
    lines.append("")
    header = "| Case | " + " | ".join(_condition_label(c) for c in conditions_order) + " | Best |"
    lines.append(header)
    lines.append("|------" + "|------" * (len(conditions_order) + 1) + "|")

    for cid in sorted(cases.keys()):
        row = f"| {cid} |"
        best = "—"
        best_val = -1
        for cond in conditions_order:
            if cond in cases[cid]:
                r = cases[cid][cond]
                if r["passed"]:
                    row += " PASS |"
                    if 1 > best_val:
                        best_val = 1
                        best = _condition_label(cond)
                else:
                    detail = f"m{r['missing']}/v{r['violations']}"
                    row += f" FAIL({detail}) |"
            else:
                row += " — |"
        row += f" {best} |"
        lines.append(row)
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    for cond in conditions_order:
        if cond == baseline:
            continue
        bl_results = [cases[cid].get(baseline) for cid in cases if baseline in cases[cid] and cond in cases[cid]]
        c_results = [cases[cid].get(cond) for cid in cases if baseline in cases[cid] and cond in cases[cid]]
        if not bl_results:
            continue
        improved = sum(1 for i in range(len(bl_results))
                       if not bl_results[i]["passed"] and c_results[i]["passed"])
        regressed = sum(1 for i in range(len(bl_results))
                        if bl_results[i]["passed"] and not c_results[i]["passed"])
        lines.append(f"- **{_condition_label(cond)}** vs {_condition_label(baseline)}: ")
        lines.append(f"  {improved} cases improved, {regressed} cases regressed")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by KDNA Lab. This report provides evidence for paper-ready comparisons.*")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def _is_passing(r: Dict) -> bool:
    """Determine if a result is passing across both domain and CLI formats."""
    if r.get("score", {}).get("L1", {}).get("passed"):
        return True
    if r.get("L1_pass"):
        return True
    if r.get("exit_ok"):
        return True
    if "exit_code" in r and "expected_exit_code" in r:
        return r["exit_code"] == r["expected_exit_code"]
    return False


def _condition_label(cond: str) -> str:
    """Human-readable condition label."""
    labels = {
        "no_kdna": "No KDNA",
        "best_prompt": "Best Prompt",
        "kdna_full": "KDNA Full",
        "kdna_compact": "KDNA Compact",
        "default": "Default",
    }
    return labels.get(cond, cond)


def report_cli():
    """CLI entry point for report generation."""
    import argparse
    from kdna_lab.paths import LAB_ROOT

    parser = argparse.ArgumentParser(description="KDNA Lab Report Generator")
    parser.add_argument("input_file", nargs="?", help="Scored results file (JSON)")
    parser.add_argument("--type", choices=["domain", "cli", "cross_model", "paper", "comparison"],
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
            print("Usage: kdna-lab-report <file> --type domain|cli|cross_model|paper")
        else:
            print("[ERROR] No data files found in outputs/")
        return

    data = json.loads(Path(args.input_file).read_text())
    report_type = args.type or auto_detect_type(args.input_file)
    out_dir = Path(args.output).parent if args.output else LAB_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(args.input_file).stem

    print(f"[INFO] Report type: {report_type}")

    if report_type == "domain":
        path = args.output or str(out_dir / f"{base_name}_domain_report.md")
        out = generate_domain_report(data, path)
    elif report_type == "cli":
        path = args.output or str(out_dir / f"{base_name}_cli_report.md")
        out = generate_cli_report(data, path)
    elif report_type == "cross_model":
        path = args.output or str(out_dir / f"{base_name}_cross_model_report.md")
        out = generate_cross_model_report(data, path)
    elif report_type == "paper":
        path = args.output or str(out_dir / f"{base_name}_paper_tables.md")
        out, csv = generate_paper_tables(data, path)
        print(f"[INFO] CSV -> {csv}")
    elif report_type == "comparison":
        path = args.output or str(out_dir / f"{base_name}_comparison.md")
        out = generate_comparison_report(data, path)
    else:
        path = args.output or str(out_dir / f"{base_name}_summary.md")
        out = generate_domain_report(data, path)

    print(f"[INFO] Report -> {out}")
