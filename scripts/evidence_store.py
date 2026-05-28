#!/usr/bin/env python3
"""
KDNA Lab — Evidence Store

Archives, indexes, and queries experiment data.
Provides a searchable catalog of all experiment runs.

Commands:
  archive   — Index a new experiment run
  list      — List all archived runs
  query     — Search runs by area, tag, status, date
  export    — Export a run's full data as a tarball
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LAB_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ROOT = LAB_ROOT / "outputs"
INDEX_FILE = EVIDENCE_ROOT / "evidence_index.json"

def load_index():
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {"runs": [], "last_updated": None}

def save_index(index):
    index["last_updated"] = datetime.now().isoformat()
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

def archive_run(run_dir, metadata=None):
    """Archive an experiment run directory."""
    run_path = Path(run_dir)
    if not run_path.exists():
        return f"Run directory not found: {run_dir}"

    # Collect metadata
    run_id = metadata.get("run_id") if metadata else run_path.name

    # Scan for artifacts
    artifacts = {
        "raw_outputs": list(run_path.glob("raw/*.txt")),
        "scores": list(run_path.glob("*score*.json")) + list(run_path.glob("*L1*.json")),
        "reports": list(run_path.glob("*.md")),
        "indexes": list(run_path.glob("*index*.json")),
        "traces": list(run_path.glob("traces/*.json")),
    }

    run_record = {
        "run_id": run_id,
        "archived_at": datetime.now().isoformat(),
        "path": str(run_path),
        "file_count": sum(len(v) for v in artifacts.values()),
        "artifacts": {k: [str(p.relative_to(run_path)) for p in v] for k, v in artifacts.items()},
        "metadata": metadata or {}
    }

    index = load_index()
    index["runs"].append(run_record)
    save_index(index)

    return run_record

def list_runs(area=None, limit=20):
    """List archived runs, optionally filtered by area."""
    index = load_index()
    runs = index["runs"]

    if area:
        runs = [r for r in runs if r.get("metadata", {}).get("area", "").lower() == area.lower()]

    runs = sorted(runs, key=lambda r: r["archived_at"], reverse=True)[:limit]
    return runs

def query_runs(**filters):
    """Query runs by arbitrary filters."""
    index = load_index()
    results = index["runs"]

    for key, value in filters.items():
        if value is None:
            continue
        if key == "area":
            results = [r for r in results if r.get("metadata", {}).get("area", "").lower() == value.lower()]
        elif key == "status":
            results = [r for r in results if r.get("metadata", {}).get("status", "").lower() == value.lower()]
        elif key == "tag":
            results = [r for r in results if value in r.get("metadata", {}).get("tags", [])]
        elif key == "before":
            results = [r for r in results if r["archived_at"] < value]
        elif key == "after":
            results = [r for r in results if r["archived_at"] > value]

    return sorted(results, key=lambda r: r["archived_at"], reverse=True)

def export_run(run_id, output_path):
    """Export a run's data as a tarball."""
    index = load_index()
    run = next((r for r in index["runs"] if r["run_id"] == run_id), None)
    if not run:
        return f"Run not found: {run_id}"

    run_path = Path(run["path"])
    if not run_path.exists():
        return f"Run directory missing: {run_path}"

    archive_path = Path(output_path) if output_path else LAB_ROOT / f"{run_id}_export.tar.gz"
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    import tarfile
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(run_path, arcname=run_id)

    return str(archive_path)

def generate_stats():
    """Generate aggregate statistics from all runs."""
    index = load_index()
    runs = index["runs"]

    stats = {
        "total_runs": len(runs),
        "total_files": sum(r["file_count"] for r in runs),
        "areas": defaultdict(int),
        "first_run": min(r["archived_at"] for r in runs) if runs else None,
        "last_run": max(r["archived_at"] for r in runs) if runs else None,
    }

    for r in runs:
        area = r.get("metadata", {}).get("area", "unknown")
        stats["areas"][area] += 1

    stats["areas"] = dict(stats["areas"])
    return stats

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Evidence Store")
    sub = parser.add_subparsers(dest="command")

    # archive
    p_archive = sub.add_parser("archive", help="Archive an experiment run")
    p_archive.add_argument("run_dir", help="Run directory to archive")
    p_archive.add_argument("--run-id", help="Run ID")
    p_archive.add_argument("--area", help="Experiment area")
    p_archive.add_argument("--tags", help="Comma-separated tags")

    # list
    p_list = sub.add_parser("list", help="List archived runs")
    p_list.add_argument("--area", help="Filter by area")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--json", action="store_true")

    # query
    p_query = sub.add_parser("query", help="Query runs")
    p_query.add_argument("--area")
    p_query.add_argument("--tag")
    p_query.add_argument("--before")
    p_query.add_argument("--after")
    p_query.add_argument("--json", action="store_true")

    # stats
    p_stats = sub.add_parser("stats", help="Show aggregate statistics")
    p_stats.add_argument("--json", action="store_true")

    # export
    p_export = sub.add_parser("export", help="Export a run as tarball")
    p_export.add_argument("run_id")
    p_export.add_argument("--output", default=None)

    args = parser.parse_args()

    if args.command == "archive":
        metadata = {}
        if args.run_id:
            metadata["run_id"] = args.run_id
        if args.area:
            metadata["area"] = args.area
        if args.tags:
            metadata["tags"] = args.tags.split(",")

        result = archive_run(args.run_dir, metadata)
        if isinstance(result, str):
            print(f"[ERROR] {result}")
        else:
            print(f"[OK] Archived run: {result['run_id']}")
            print(f"     Files: {result['file_count']}")
            print(f"     Path: {result['path']}")

    elif args.command == "list":
        runs = list_runs(area=args.area, limit=args.limit)
        if args.json:
            print(json.dumps(runs, indent=2, ensure_ascii=False))
        else:
            print(f"Archived runs ({len(runs)}):")
            for r in runs:
                area = r.get("metadata", {}).get("area", "?")
                print(f"  {r['run_id']:30s} [{area}] {r['file_count']} files  {r['archived_at'][:10]}")

    elif args.command == "query":
        runs = query_runs(
            area=args.area, tag=args.tag,
            before=args.before, after=args.after
        )
        if args.json:
            print(json.dumps(runs, indent=2, ensure_ascii=False))
        else:
            print(f"Query results ({len(runs)}):")
            for r in runs:
                print(f"  {r['run_id']:30s} {r['archived_at'][:10]}")

    elif args.command == "stats":
        stats = generate_stats()
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print("KDNA Lab Evidence Store Statistics")
            print(f"  Total runs: {stats['total_runs']}")
            print(f"  Total files: {stats['total_files']}")
            print(f"  First run: {stats['first_run'][:10] if stats['first_run'] else 'N/A'}")
            print(f"  Last run: {stats['last_run'][:10] if stats['last_run'] else 'N/A'}")
            print(f"  By area:")
            for area, count in sorted(stats['areas'].items()):
                print(f"    {area}: {count}")

    elif args.command == "export":
        path = export_run(args.run_id, args.output)
        if path.startswith("Run not"):
            print(f"[ERROR] {path}")
        else:
            print(f"[OK] Exported → {path}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
