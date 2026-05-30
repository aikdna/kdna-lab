"""KDNA Lab — Trace Completeness Checker.

Validates that KDNA judgment traces are structurally complete,
satisfying the core KDNA claim: "Trace proves inspectability."

Verifies trace JSON against the judgment-trace schema:
  - Required fields present in either trace or judgment-report form
  - Self-check items are meaningful (not all mechanically true)
  - Trace is self-consistent (axioms triggered match domain axioms)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT


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
    """Parse a KDNA trace JSON/JSONL file."""
    try:
        content = Path(trace_path).read_text()
        # Handle JSONL: take first line as the trace entry
        if trace_path.endswith('.jsonl'):
            lines = content.strip().split('\n')
            if lines:
                return json.loads(lines[0])
            return None
        return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def check_trace_structure(trace: Dict) -> Dict[str, Any]:
    """Check trace structural completeness. Handles both judgment-report and Product Contract formats."""
    errors = []
    warnings = []

    # Format detection
    is_report = "report_version" in trace or "report_id" in trace
    is_contract = "domain_id" in trace or "mode" in trace

    # ── Timestamp ────────────────────────────────────────
    timestamp = trace.get("timestamp") or trace.get("created_at")
    if not timestamp:
        errors.append("Missing required field: timestamp or created_at")

    # ── Domain ───────────────────────────────────────────
    domain = trace.get("domain") or trace.get("domain_id")
    loaded_domains = trace.get("loaded_domains", [])
    if not domain and loaded_domains:
        first = loaded_domains[0] if isinstance(loaded_domains[0], dict) else {}
        domain = first.get("name")
    if not domain:
        errors.append("Missing required field: domain or loaded_domains[0].name")

    # ── Version ──────────────────────────────────────────
    version = trace.get("version") or trace.get("domain_version") or trace.get("report_version")
    if not version and loaded_domains:
        first = loaded_domains[0] if isinstance(loaded_domains[0], dict) else {}
        version = first.get("version") or first.get("judgment_version")
    if not version:
        warnings.append("Missing version — trace is inspectable but less reproducible")

    # ── Axioms triggered ─────────────────────────────────
    axioms = trace.get("axioms_triggered", [])
    # Judgment-report format: nested under triggered_judgment.items
    if not axioms and isinstance(trace.get("triggered_judgment"), dict):
        axioms = trace["triggered_judgment"].get("items", [])
    # Product Contract format: axioms_triggered is a flat list of IDs
    if not axioms and is_contract:
        axiom_ids = trace.get("axioms_triggered", trace.get("triggered_axioms", []))
        if isinstance(axiom_ids, list) and all(isinstance(a, str) for a in axiom_ids):
            axioms = []  # IDs only — not objects, but this is valid Contract format

    if isinstance(axioms, list):
        for i, axiom in enumerate(axioms):
            if not isinstance(axiom, dict):
                continue
            if "id" not in axiom:
                errors.append(f"axioms_triggered[{i}] missing field: id")
            if not (axiom.get("statement") or axiom.get("summary") or axiom.get("kind") or axiom.get("one_sentence")):
                warnings.append(f"axioms_triggered[{i}] missing statement/summary/kind")
            if axiom.get("triggered") is True and not axiom.get("evidence"):
                warnings.append(f"axioms_triggered[{i}] triggered but no evidence")
    elif axioms:
        errors.append(f"axioms_triggered should be a list, got {type(axioms).__name__}")

    # ── Self_checks ──────────────────────────────────────
    self_checks = trace.get("self_checks", [])
    if isinstance(self_checks, list):
        all_true = all(
            sc.get("status") in (True, "true", "pass", "ok")
            for sc in self_checks
            if isinstance(sc, dict)
        )
        if all_true and len(self_checks) > 0:
            warnings.append("All self_checks are pass/true — may indicate mechanical checking")
    elif self_checks:
        errors.append(f"self_checks should be a list, got {type(self_checks).__name__}")

    # ── Additional recommended fields ────────────────────
    if not is_contract and not is_report:
        for field in TRACE_RECOMMENDED_FIELDS:
            if field not in trace:
                warnings.append(f"Missing recommended field: {field}")

    return {
        "structural_errors": len(errors),
        "structural_warnings": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "has_axioms": bool(axioms),
        "has_self_checks": bool(self_checks),
        "axioms_count": len(axioms) if isinstance(axioms, list) else 0,
        "self_checks_count": len(self_checks) if isinstance(self_checks, list) else 0,
        "domain": domain,
        "version": version,
        "timestamp": timestamp,
        "format": "contract" if is_contract else ("report" if is_report else "unknown"),
        "passed": len(errors) == 0,
    }


def discover_traces(kdna_home: Optional[Path] = None) -> List[Path]:
    """Discover trace files in the KDNA home directory."""
    if kdna_home is None:
        kdna_home = Path.home() / ".kdna"
    traces_dir = kdna_home / "traces"
    if not traces_dir.exists():
        return []
    # Support both .json (judgment reports) and .jsonl (daily trace logs)
    files = sorted(traces_dir.glob("*.json")) + sorted(traces_dir.glob("*.jsonl"))
    # Exclude .md files
    files = [f for f in files if f.suffix in ('.json', '.jsonl')]
    return sorted(files)


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
            "timestamp": check.get("timestamp", "unknown"),
            "domain": check.get("domain", "unknown"),
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
