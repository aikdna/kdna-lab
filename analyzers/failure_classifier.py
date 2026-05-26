#!/usr/bin/env python3
"""
KDNA Lab — Failure Classifier

Reads scored experiment outputs, classifies failures into known categories,
clusters similar failures, and generates fix suggestions.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

LAB_ROOT = Path(__file__).resolve().parent.parent

FAILURE_TYPES = {
    "schema_doc_mismatch": {
        "description": "SPEC documentation doesn't match JSON Schema requirements",
        "fix_area": "spec/schema",
        "suggestion_template": "Align SPEC.md field documentation with JSON Schema. Add type examples for {field}."
    },
    "cli_error_unclear": {
        "description": "CLI error message doesn't help the user fix the problem",
        "fix_area": "cli",
        "suggestion_template": "Improve error message for '{command}': include expected type, example, and fix guidance."
    },
    "canonical_phrase_missing": {
        "description": "Required canonical phrase not present in output",
        "fix_area": "domain/loader",
        "suggestion_template": "Add REQUIRED_OUTPUT block to kdna load or mark phrase with output_required: true in domain."
    },
    "banned_claim_leak": {
        "description": "Banned terms or claims appeared in output",
        "fix_area": "domain",
        "suggestion_template": "Strengthen banned_terms in domain. Add to must_not_include in eval cases."
    },
    "fact_fabrication": {
        "description": "Agent fabricated data without source materials",
        "fix_area": "domain",
        "suggestion_template": "Add required_source_materials field. Add fact_discipline axiom if missing."
    },
    "trace_incomplete": {
        "description": "Judgment trace missing required fields",
        "fix_area": "runtime",
        "suggestion_template": "Check runtime contract compliance. Ensure trace includes domain, axioms_triggered, self_checks."
    },
    "domain_misrouting": {
        "description": "Wrong domain loaded or domain not activated for matching input",
        "fix_area": "loader/runtime",
        "suggestion_template": "Check trigger_signals in KDNA_Scenarios.json. Verify kdna match behavior."
    },
    "license_bypass": {
        "description": "License or access control mechanism was bypassed",
        "fix_area": "security/license",
        "suggestion_template": "Review license enforcement in runtime. Check signature verification and entitlement checks."
    },
    "registry_integrity_failure": {
        "description": "Registry returned tampered or invalid domain package",
        "fix_area": "registry",
        "suggestion_template": "Verify SHA256 checksums. Check signature validation pipeline. Review registry CI."
    },
    "cross_model_inconsistency": {
        "description": "Same domain produced materially different behavior across models",
        "fix_area": "domain/loader",
        "suggestion_template": "Add REQUIRED_OUTPUT section. Test cananical phrase retention. Use load profiles."
    },
    "self_check_misleading": {
        "description": "Self-check answers are mechanically all-true without real assessment",
        "fix_area": "domain/schema",
        "suggestion_template": "Support true/false/partial/n/a status with notes. Add self_check_audit to test protocol."
    },
    "figure_not_argumentative": {
        "description": "Figure plan is decorative rather than argument-driven",
        "fix_area": "domain",
        "suggestion_template": "Strengthen output_profiles.figure_plan schema. Require argument_role field."
    },
    "json_invalid": {
        "description": "Expected JSON output is malformed or wrapped in markdown",
        "fix_area": "domain",
        "suggestion_template": "Add structured_output test case. Require raw JSON without markdown fences."
    },
    "exit_code_mismatch": {
        "description": "CLI exit code doesn't match expectation",
        "fix_area": "cli",
        "suggestion_template": "Check CLI exit code specification. Document expected codes for error states."
    },
    "install_failure": {
        "description": "Domain installation failed",
        "fix_area": "cli/registry",
        "suggestion_template": "Check network, registry cache, or local package integrity. Verify CLI version compatibility."
    }
}

def classify_failure(case_id, score, output_summary=""):
    """Classify a single failure into known types."""
    classifications = []

    if "score" in score and "L1" in score["score"]:
        l1 = score["score"]["L1"]
        checks = l1.get("checks", {})

        if "must_include" in checks:
            missing = checks["must_include"].get("missing", [])
            if missing:
                classifications.append({
                    "type": "canonical_phrase_missing",
                    "evidence": f"Missing: {missing}",
                    "confidence": "high"
                })

        if "must_not_include" in checks:
            violations = checks["must_not_include"].get("violations", [])
            if violations:
                classifications.append({
                    "type": "banned_claim_leak",
                    "evidence": f"Violations: {violations}",
                    "confidence": "high"
                })

        if "json_valid" in checks and not checks["json_valid"].get("passed"):
            classifications.append({
                "type": "json_invalid",
                "evidence": checks["json_valid"].get("detail", ""),
                "confidence": "high"
            })

    return classifications

def cluster_by_type(failures):
    """Group failures by type."""
    clusters = defaultdict(list)
    for f in failures:
        for c in f.get("classifications", []):
            clusters[c["type"]].append({
                "case_id": f["case_id"],
                "evidence": c["evidence"]
            })
    return dict(clusters)

def generate_suggestions(clusters):
    """Generate fix suggestions for each failure cluster."""
    suggestions = []
    for failure_type, cases in clusters.items():
        info = FAILURE_TYPES.get(failure_type, {})
        suggestion = {
            "failure_type": failure_type,
            "description": info.get("description", "Unknown failure type"),
            "count": len(cases),
            "affected_cases": [c["case_id"] for c in cases],
            "fix_area": info.get("fix_area", "unknown"),
            "suggestion": info.get("suggestion_template", "Investigate and fix.").format(
                field=", ".join(set(str(c.get("evidence", "")) for c in cases))
            )
        }
        suggestions.append(suggestion)
    return sorted(suggestions, key=lambda s: s["count"], reverse=True)

def analyze(score_file, output_dir=None, quiet=False):
    """Main entry: analyze scored outputs and produce failure report."""
    log = sys.stderr if quiet else sys.stdout
    with open(score_file) as f:
        data = json.load(f) if score_file.endswith(".json") else None

    if data is None:
        return {"error": "Only JSON score files are supported."}

    # Normalize input: accept list, dict with "results", or dict with "runs"
    if isinstance(data, list):
        scores = data
    elif isinstance(data, dict):
        if "results" in data:
            scores = data["results"]
        elif "runs" in data:
            return {"error": "Input is evidence index (runs), not scored results. Use rule_scorer.py --json output."}
        else:
            scores = [data]
    else:
        return {"error": f"Unexpected data type: {type(data).__name__}"}

    failures = []
    for s in scores:
        if not isinstance(s, dict):
            continue

        # Handle both format variants: score.L1.passed (nested) and L1_passed (flat)
        l1_passed = s.get("score", {}).get("L1", {}).get("passed")
        if l1_passed is None:
            l1_passed = s.get("L1_passed", True)
        if l1_passed:
            continue

        cid = s.get("case_id") or s.get("id", "unknown")
        # Build a score-compatible wrapper for classify_failure
        wrapper = {"score": {"L1": s.get("score", {}).get("L1", s)}} if "score" in s else {"score": {"L1": s}}
        classifications = classify_failure(cid, wrapper)
        failures.append({
            "case_id": cid,
            "classifications": classifications
        })

    clusters = cluster_by_type(failures)
    suggestions = generate_suggestions(clusters)

    report = {
        "total_cases": len(scores),
        "failed_cases": len(failures),
        "failure_clusters": len(clusters),
        "clusters": clusters,
        "suggestions": suggestions
    }

    if output_dir:
        output_path = Path(output_dir) / f"failure_analysis_{Path(score_file).stem}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Failure analysis → {output_path}", file=log)

    return report

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Failure Classifier")
    parser.add_argument("score_file", help="Scored results file (JSON)")
    parser.add_argument("--output-dir", default=None, help="Output directory for analysis")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    output_dir = args.output_dir or str(LAB_ROOT / "outputs" / "failures")
    report = analyze(args.score_file, output_dir, quiet=args.json)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"\nFailure Analysis:")
        print(f"  Total cases: {report.get('total_cases', 'N/A')}")
        print(f"  Failed: {report.get('failed_cases', 0)}")
        print(f"  Clusters: {report.get('failure_clusters', 0)}")
        if report.get("suggestions"):
            print(f"\n  Suggestions:")
            for s in report["suggestions"]:
                print(f"  [{s['count']}x] {s['failure_type']} → {s['fix_area']}")
                print(f"       {s['suggestion']}")

if __name__ == "__main__":
    main()
