"""KDNA Lab — Domain Evolution Tracker.

Tracks domain version evolution: changes between versions,
regression detection, and the Human Lock governance cycle.

This implements the "Hypothesis → Patch → Regression → Human Lock" loop
from the KDNA Lab architecture.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


EVOLUTION_RECORD_VERSION = "1.0"


def create_evolution_record(
    domain: str,
    version_from: str,
    version_to: str,
    changes: List[Dict[str, str]],
    author: str = "kdna-lab",
) -> Dict[str, Any]:
    """Create a structured evolution record for a domain version bump.

    Args:
        domain: Domain name
        version_from: Previous version
        version_to: New version
        changes: List of {"type": "axiom|pattern|scenario|terminology|schema", "description": "..."}
        author: Change author
    """
    return {
        "format": "kdna-evolution-record",
        "version": EVOLUTION_RECORD_VERSION,
        "domain": domain,
        "version_from": version_from,
        "version_to": version_to,
        "timestamp": datetime.now().isoformat(),
        "author": author,
        "changes": changes,
        "human_lock": {
            "status": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "verdict": None,
            "reason": None,
        },
        "regression": {
            "status": "pending",
            "tests_run": 0,
            "tests_passed": 0,
            "regressions": [],
        },
    }


def apply_human_lock(
    record: Dict,
    reviewer: str,
    verdict: str,
    reason: str,
) -> Dict:
    """Apply a Human Lock verdict to an evolution record."""
    record["human_lock"] = {
        "status": "locked" if verdict == "approved" else "rejected",
        "reviewer": reviewer,
        "reviewed_at": datetime.now().isoformat(),
        "verdict": verdict,
        "reason": reason,
    }
    return record


def record_regression_results(
    record: Dict,
    tests_run: int,
    tests_passed: int,
    regressions: List[str],
) -> Dict:
    """Record regression test results for an evolution record."""
    record["regression"] = {
        "status": "passed" if len(regressions) == 0 else "failed",
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "regressions": regressions,
    }
    return record


def compute_evolution_summary(records: List[Dict]) -> Dict[str, Any]:
    """Compute summary statistics from a list of evolution records."""
    if not records:
        return {"total_versions": 0, "total_changes": 0}

    total_versions = len(set(
        r["version_to"] for r in records
    ))
    total_changes = sum(len(r.get("changes", [])) for r in records)
    locked_count = sum(
        1 for r in records
        if r.get("human_lock", {}).get("status") == "locked"
    )
    regression_passes = sum(
        1 for r in records
        if r.get("regression", {}).get("status") == "passed"
    )

    change_types: Dict[str, int] = {}
    for r in records:
        for c in r.get("changes", []):
            t = c.get("type", "unknown")
            change_types[t] = change_types.get(t, 0) + 1

    return {
        "total_versions": total_versions,
        "total_changes": total_changes,
        "locked_count": locked_count,
        "regression_passes": regression_passes,
        "regression_fails": len(records) - regression_passes,
        "change_types": change_types,
    }


def generate_evolution_report(
    domain: str,
    records: List[Dict],
    output_path: str,
) -> str:
    """Generate a domain evolution history report."""
    summary = compute_evolution_summary(records)

    lines = []
    lines.append(f"# Domain Evolution Report: {domain}")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Versions tracked:** {summary['total_versions']}")
    lines.append(f"**Total changes:** {summary['total_changes']}")
    lines.append(f"**Human Locks:** {summary['locked_count']}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Versions | {summary['total_versions']} |")
    lines.append(f"| Changes | {summary['total_changes']} |")
    lines.append(f"| Human Locks | {summary['locked_count']} |")
    lines.append(f"| Regression passes | {summary['regression_passes']} |")
    lines.append("")

    if summary.get("change_types"):
        lines.append("## Change Types")
        lines.append("")
        for ct, count in sorted(summary["change_types"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{ct}**: {count}")
        lines.append("")

    lines.append("## Version History")
    lines.append("")
    for r in sorted(records, key=lambda x: x["timestamp"], reverse=True):
        lock = r.get("human_lock", {})
        reg = r.get("regression", {})

        lock_icon = "🔒" if lock.get("status") == "locked" else ("❌" if lock.get("status") == "rejected" else "⏳")
        reg_icon = "✅" if reg.get("status") == "passed" else ("❌" if reg.get("status") == "failed" else "⏳")

        lines.append(f"### {r['version_from']} → {r['version_to']}")
        lines.append(f"- **Date:** {r['timestamp'][:10]}")
        lines.append(f"- **Author:** {r['author']}")
        lines.append(f"- **Human Lock:** {lock_icon} {lock.get('verdict', 'pending')}")
        lines.append(f"- **Regression:** {reg_icon} {reg.get('tests_passed', 0)}/{reg.get('tests_run', 0)}")
        lines.append(f"- **Changes ({len(r.get('changes', []))}):**")
        for c in r.get("changes", []):
            lines.append(f"  - [{c.get('type', '?')}] {c.get('description', '')}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by KDNA Lab Domain Evolution Tracker.*")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def evolution_cli():
    """CLI entry point for domain evolution."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Domain Evolution Tracker")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Create evolution record")
    create_p.add_argument("domain")
    create_p.add_argument("--from-version", required=True)
    create_p.add_argument("--to-version", required=True)
    create_p.add_argument("--changes", default="[]", help="JSON array of changes")
    create_p.add_argument("--output", default=None)

    lock_p = sub.add_parser("lock", help="Apply Human Lock")
    lock_p.add_argument("record_file")
    lock_p.add_argument("--reviewer", required=True)
    lock_p.add_argument("--verdict", choices=["approved", "rejected"], required=True)
    lock_p.add_argument("--reason", default="")

    reg_p = sub.add_parser("regression", help="Record regression results")
    reg_p.add_argument("record_file")
    reg_p.add_argument("--run", type=int, default=0)
    reg_p.add_argument("--passed", type=int, default=0)
    reg_p.add_argument("--regressions", default="[]")

    summary_p = sub.add_parser("summary", help="Summarize all evolution records")
    summary_p.add_argument("records", nargs="+", help="Evolution record JSON files")

    args = parser.parse_args()

    if args.command == "create":
        changes = json.loads(args.changes)
        record = create_evolution_record(
            args.domain, args.from_version, args.to_version, changes,
        )
        out_path = args.output or f"evolution_{args.domain.replace('@','').replace('/','_')}_{args.to_version}.json"
        Path(out_path).write_text(json.dumps(record, indent=2, ensure_ascii=False))
        print(f"[EVOLUTION] Record → {out_path}")
        print(f"  {args.from_version} → {args.to_version}: {len(changes)} changes, human lock pending")

    elif args.command == "lock":
        record = json.loads(Path(args.record_file).read_text())
        record = apply_human_lock(record, args.reviewer, args.verdict, args.reason)
        Path(args.record_file).write_text(json.dumps(record, indent=2, ensure_ascii=False))
        print(f"[LOCK] {args.verdict} by {args.reviewer}")

    elif args.command == "regression":
        record = json.loads(Path(args.record_file).read_text())
        regressions = json.loads(args.regressions) if args.regressions else []
        record = record_regression_results(record, args.run, args.passed, regressions)
        Path(args.record_file).write_text(json.dumps(record, indent=2, ensure_ascii=False))
        print(f"[REG] {args.passed}/{args.run} passed, {len(regressions)} regressions")

    elif args.command == "summary":
        records = []
        for f in args.records:
            records.append(json.loads(Path(f).read_text()))
        domain = records[0].get("domain", "unknown") if records else "unknown"
        out_path = f"evolution_{domain.replace('@','').replace('/','_')}_summary.md"
        path = generate_evolution_report(domain, records, out_path)
        print(f"[SUMMARY] {path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    evolution_cli()
