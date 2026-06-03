#!/usr/bin/env python3
"""Generate L3 human review sheet from scored benchmark artifacts."""
import json, csv, sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent

def generate(domain: str, output_path: str):
    artifact_dir = LAB_ROOT / "benchmarks" / "reference-domains" / domain / "2026-06-03" / "raw"
    case_file = LAB_ROOT / "examples" / domain / "cases.jsonl"

    if not artifact_dir.exists():
        print(f"SKIP: {artifact_dir} not found")
        return

    scored_files = sorted(artifact_dir.glob("*_benchmark-run-v1.scored.json"))
    if not scored_files:
        print(f"SKIP: no scored artifacts in {artifact_dir}")
        return

    cases = {}
    if case_file.exists():
        with open(case_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                c = json.loads(line)
                cases[c["id"]] = c

    latest = scored_files[-1]
    with open(latest) as f:
        artifact = json.load(f)

    rows = []
    for entry in artifact.get("cases", []):
        cid = entry["case_id"]
        case = cases.get(cid, {})
        l1 = entry.get("scores", {}).get("L1", {})
        l2 = entry.get("scores", {}).get("L2", {})
        rows.append({
            "case_id": cid,
            "condition": entry.get("condition", ""),
            "input": case.get("input", "")[:300],
            "expected_behavior": case.get("expected_behavior", entry.get("expected_behavior", ""))[:200],
            "output": entry.get("output", "")[:500],
            "L1_pass": l1.get("passed"),
            "L2_pass": l2.get("passed"),
            "L2_status": l2.get("status", "scored"),
            "L2_summary": l2.get("summary", ""),
            "error": entry.get("error", ""),
            "L3_verdict": "",
            "L3_notes": "",
        })

    out_path = Path(output_path) / f"{domain}_l3_review_sheet.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "condition", "input", "expected_behavior",
            "output", "L1_pass", "L2_pass", "L2_status", "L2_summary", "error", "L3_verdict", "L3_notes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {out_path}: {len(rows)} rows")

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else LAB_ROOT / "benchmarks" / "reference-domains"
    for domain in ["writing", "prompt_diagnosis", "agent_safety"]:
        generate(domain, str(out))
