#!/usr/bin/env python3
"""
KDNA Lab — Regression Analyzer

Compares two experiment runs (e.g., domain v1 vs v2) and identifies:
- Improvements (failures that became passing)
- Regressions (passing cases that became failing)
- Unchanged (same result in both versions)
- New cases (only in v2)
- Removed cases (only in v1)
"""

import json
import os
from pathlib import Path
from datetime import datetime

LAB_ROOT = Path(__file__).resolve().parent.parent

def load_scores(score_file):
    """Load scored results from JSON file."""
    if not os.path.exists(score_file):
        return None
    with open(score_file) as f:
        data = json.load(f)
    # Handle both formats: array of scored items or dict with 'results'
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return [data]

def compare_runs(v1_file, v2_file, case_file=None):
    v1_scores = load_scores(v1_file)
    v2_scores = load_scores(v2_file)

    if v1_scores is None:
        return {"error": f"v1 file not found: {v1_file}"}
    if v2_scores is None:
        return {"error": f"v2 file not found: {v2_file}"}

    # Normalize to dict keyed by case_id
    def normalize(scores):
        d = {}
        for s in scores:
            cid = s.get("case_id", s.get("id", "unknown"))
            passed = False
            if "score" in s and "L1" in s["score"]:
                passed = s["score"]["L1"].get("passed", False)
            elif "L1_pass" in s:
                passed = s["L1_pass"]
            elif "passed" in s:
                passed = s["passed"]
            elif "exit_code" in s and "expected_exit_code" in s:
                passed = s["exit_code"] == s["expected_exit_code"]
            d[cid] = passed
        return d

    v1 = normalize(v1_scores)
    v2 = normalize(v2_scores)

    all_cases = set(list(v1.keys()) + list(v2.keys()))

    improvements = []  # v1 fail → v2 pass
    regressions = []   # v1 pass → v2 fail
    unchanged_pass = []
    unchanged_fail = []
    new_cases = []     # only in v2
    removed_cases = [] # only in v1

    for cid in all_cases:
        in_v1 = cid in v1
        in_v2 = cid in v2

        if in_v1 and in_v2:
            p1 = v1[cid]
            p2 = v2[cid]
            if not p1 and p2:
                improvements.append(cid)
            elif p1 and not p2:
                regressions.append(cid)
            elif p1 and p2:
                unchanged_pass.append(cid)
            else:
                unchanged_fail.append(cid)
        elif in_v2:
            new_cases.append(cid)
        else:
            removed_cases.append(cid)

    total = len(all_cases)
    v1_pass = sum(1 for p in v1.values() if p)
    v2_pass = sum(1 for p in v2.values() if p)

    return {
        "v1_file": v1_file,
        "v2_file": v2_file,
        "v1_total": len(v1),
        "v2_total": len(v2),
        "v1_pass_rate": f"{v1_pass}/{len(v1)} ({v1_pass/len(v1)*100:.0f}%)" if v1 else "N/A",
        "v2_pass_rate": f"{v2_pass}/{len(v2)} ({v2_pass/len(v2)*100:.0f}%)" if v2 else "N/A",
        "improvements": improvements,
        "regressions": regressions,
        "unchanged_pass": unchanged_pass,
        "unchanged_fail": unchanged_fail,
        "new_cases": new_cases,
        "removed_cases": removed_cases,
        "summary": {
            "improved": len(improvements),
            "regressed": len(regressions),
            "unchanged_pass": len(unchanged_pass),
            "unchanged_fail": len(unchanged_fail),
            "new": len(new_cases),
            "removed": len(removed_cases)
        }
    }

def generate_report(comparison, output_path):
    c = comparison
    lines = []
    lines.append("# Regression Analysis Report")
    lines.append("")
    lines.append(f"**v1:** `{Path(c['v1_file']).name}`")
    lines.append(f"**v2:** `{Path(c['v2_file']).name}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | v1 | v2 | Change |")
    lines.append(f"|--------|----|----|--------|")
    lines.append(f"| Total cases | {c['v1_total']} | {c['v2_total']} | {c['v2_total'] - c['v1_total']:+d} |")
    lines.append(f"| Pass rate | {c['v1_pass_rate']} | {c['v2_pass_rate']} | — |")
    lines.append("")

    s = c["summary"]
    lines.append("## Changes")
    lines.append("")
    lines.append(f"| Category | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| ✅ Improved (fail→pass) | {s['improved']} |")
    lines.append(f"| ❌ Regressed (pass→fail) | {s['regressed']} |")
    lines.append(f"| ➖ Unchanged (pass) | {s['unchanged_pass']} |")
    lines.append(f"| ➖ Unchanged (fail) | {s['unchanged_fail']} |")
    lines.append(f"| 🆕 New cases | {s['new']} |")
    lines.append(f"| 🗑 Removed cases | {s['removed']} |")
    lines.append("")

    if c["improvements"]:
        lines.append("## Improvements")
        for cid in c["improvements"]:
            lines.append(f"- ✅ {cid}")
        lines.append("")

    if c["regressions"]:
        lines.append("## ⚠️ Regressions")
        for cid in c["regressions"]:
            lines.append(f"- ❌ {cid}")
        lines.append("")
        lines.append("**Action required:** Investigate why these cases regressed.")
        lines.append("")

    if c["unchanged_fail"]:
        lines.append("## Still Failing")
        for cid in c["unchanged_fail"]:
            lines.append(f"- {cid}")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Regression Analyzer")
    parser.add_argument("v1_file", nargs="?", help="v1 score file (baseline)")
    parser.add_argument("v2_file", nargs="?", help="v2 score file (comparison)")
    parser.add_argument("--output", default=None, help="Report output path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.v1_file or not args.v2_file:
        outputs_dir = LAB_ROOT / "outputs"
        score_files = sorted(outputs_dir.glob("*.json"))
        scores_dir = outputs_dir / "scores"
        if scores_dir.exists():
            score_files += sorted(scores_dir.glob("*.json"))
        if len(score_files) >= 2:
            args.v1_file = str(score_files[-2])
            args.v2_file = str(score_files[-1])
            print(f"[INFO] Auto-detected: v1={Path(args.v1_file).name}, v2={Path(args.v2_file).name}")
        else:
            print("[ERROR] Need at least 2 score files. Provide v1 and v2 paths.")
            return

    comparison = compare_runs(args.v1_file, args.v2_file)

    if "error" in comparison:
        print(f"[ERROR] {comparison['error']}")
        return

    if args.json:
        print(json.dumps(comparison, indent=2, ensure_ascii=False))
    else:
        output_path = args.output or str(LAB_ROOT / "reports" / f"regression_{Path(args.v2_file).stem}.md")
        report_path = generate_report(comparison, output_path)
        print(f"[INFO] Report → {report_path}")

        s = comparison["summary"]
        print(f"\n  v1 pass: {comparison['v1_pass_rate']}")
        print(f"  v2 pass: {comparison['v2_pass_rate']}")
        print(f"  ✅ Improved: {s['improved']}  ❌ Regressed: {s['regressed']}  ➖ Unchanged: {s['unchanged_pass'] + s['unchanged_fail']}")

if __name__ == "__main__":
    main()
