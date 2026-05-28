"""KDNA Lab — Evidence Store.

Structured archival system for all KDNA Lab experiment data.
Every run, score, trace, and failure is stored in a queryable archive.

Philosophy: Evidence Over Claims.
This store is the single source of truth for all KDNA validation data.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class EvidenceStore:
    """Persistent archive of all KDNA Lab experiment artifacts.

    Directory structure:
        evidence/
            runs/
                {run_id}/
                    run.json        — full run metadata
                    index.json      — case result index
                    raw/            — raw outputs
                    scores/         — scored results
            domains/
                {domain}/
                    timeline.json   — all runs for this domain
            paper/
                tables/             — exported paper tables
                figures/            — plot data
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in ["runs", "domains", "paper/tables", "paper/figures"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    @property
    def domains_dir(self) -> Path:
        return self.root / "domains"

    @property
    def paper_dir(self) -> Path:
        return self.root / "paper"

    # ---- Ingest ----

    def ingest_run(
        self,
        run_id: str,
        run_type: str,
        target: str,
        results: List[Dict[str, Any]],
        raw_dir: Optional[Path] = None,
        conditions: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Archive a completed experiment run.

        Args:
            run_id: Unique run identifier (e.g. run_20260528_120000)
            run_type: 'domain', 'cli', 'cross_model', 'schema', 'registry'
            target: Subject under test (domain name, CLI command)
            results: List of scored results
            raw_dir: Optional path to raw output files to copy
            conditions: Experiment conditions used
            models: Models used
            extra_meta: Additional metadata

        Returns: Path to the archived run directory.
        """
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        summary = self._compute_summary(results)

        meta = {
            "run_id": run_id,
            "type": run_type,
            "target": target,
            "timestamp": datetime.now().isoformat(),
            "conditions": conditions or [],
            "models": models or [],
            "total_cases": len(results),
            **summary,
        }
        if extra_meta:
            meta.update(extra_meta)

        (run_dir / "run.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False)
        )

        (run_dir / "index.json").write_text(
            json.dumps([self._serialize_result(r) for r in results], indent=2, ensure_ascii=False)
        )

        if raw_dir and Path(raw_dir).exists():
            raw_target = run_dir / "raw"
            raw_target.mkdir(exist_ok=True)
            for f in Path(raw_dir).glob("*"):
                if f.is_file():
                    shutil.copy2(f, raw_target / f.name)

        self._update_domain_timeline(target, run_id, summary)

        return run_dir

    def _compute_summary(self, results: List[Dict]) -> Dict[str, Any]:
        total = len(results)
        if total == 0:
            return {"passed": 0, "failed": 0, "pass_rate": 0, "by_condition": {}}

        passed = 0
        by_condition: Dict[str, Dict] = {}

        for r in results:
            l1_pass = (
                r.get("score", {}).get("L1", {}).get("passed")
                or r.get("L1_pass")
                or r.get("exit_ok")
            )
            if l1_pass:
                passed += 1

            cond = r.get("condition", "default")
            if cond not in by_condition:
                by_condition[cond] = {"total": 0, "passed": 0}
            by_condition[cond]["total"] += 1
            if l1_pass:
                by_condition[cond]["passed"] += 1

        for cond, stats in by_condition.items():
            stats["pass_rate"] = round(stats["passed"] / stats["total"] * 100) if stats["total"] else 0

        return {
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100),
            "by_condition": by_condition,
        }

    def _serialize_result(self, r: Dict) -> Dict:
        return {
            "case_id": r.get("case_id", "?"),
            "condition": r.get("condition", ""),
            "model": r.get("model", ""),
            "L1_pass": (
                r.get("score", {}).get("L1", {}).get("passed")
                or r.get("L1_pass")
                or r.get("exit_ok")
            ),
            "missing": r.get("missing", []),
            "violations": r.get("violations", []),
            "output_path": str(r.get("output_path", "")),
        }

    def _update_domain_timeline(self, domain: str, run_id: str, summary: Dict):
        timeline_path = self.domains_dir / domain / "timeline.json"
        timeline_path.parent.mkdir(parents=True, exist_ok=True)

        timeline = []
        if timeline_path.exists():
            timeline = json.loads(timeline_path.read_text())

        timeline.append({
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            **summary,
        })

        timeline_path.write_text(json.dumps(timeline, indent=2, ensure_ascii=False))

    # ---- Query ----

    def list_runs(
        self,
        run_type: Optional[str] = None,
        target: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """List archived runs, optionally filtered."""
        runs = []
        for run_dir in sorted(self.runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "run.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text())
            if run_type and meta.get("type") != run_type:
                continue
            if target and target not in meta.get("target", ""):
                continue
            runs.append(meta)
            if len(runs) >= limit:
                break
        return runs

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get full details of a single run."""
        meta_path = self.runs_dir / run_id / "run.json"
        idx_path = self.runs_dir / run_id / "index.json"
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text())
        if idx_path.exists():
            meta["results"] = json.loads(idx_path.read_text())
        return meta

    def domain_timeline(self, domain: str) -> List[Dict]:
        """Get pass rates over time for a domain."""
        timeline_path = self.domains_dir / domain / "timeline.json"
        if not timeline_path.exists():
            return []
        return json.loads(timeline_path.read_text())

    def compare_runs(self, run_id_1: str, run_id_2: str) -> Dict:
        """Compare two runs and identify changes."""
        r1 = self.get_run(run_id_1)
        r2 = self.get_run(run_id_2)
        if not r1 or not r2:
            return {"error": "One or both runs not found"}

        results1 = {r["case_id"]: r for r in (r1.get("results") or [])}
        results2 = {r["case_id"]: r for r in (r2.get("results") or [])}

        all_cases = set(list(results1.keys()) + list(results2.keys()))
        improved = []
        regressed = []
        unchanged_pass = []
        unchanged_fail = []

        for cid in sorted(all_cases):
            r1_pass = results1.get(cid, {}).get("L1_pass", False)
            r2_pass = results2.get(cid, {}).get("L1_pass", False)
            if not r1_pass and r2_pass:
                improved.append(cid)
            elif r1_pass and not r2_pass:
                regressed.append(cid)
            elif r1_pass and r2_pass:
                unchanged_pass.append(cid)
            else:
                unchanged_fail.append(cid)

        p1 = r1.get("pass_rate", 0)
        p2 = r2.get("pass_rate", 0)

        return {
            "run_1": run_id_1,
            "run_2": run_id_2,
            "pass_rate_1": p1,
            "pass_rate_2": p2,
            "delta": p2 - p1,
            "improved": improved,
            "regressed": regressed,
            "unchanged_pass": len(unchanged_pass),
            "unchanged_fail": len(unchanged_fail),
            "total": len(all_cases),
        }

    # ---- Export ----

    def export_paper_data(self, domain: str, output_dir: Optional[Path] = None) -> Tuple[Path, Path]:
        """Export paper-ready CSV and Markdown tables for a domain."""
        od = output_dir or self.paper_dir / "tables"
        od.mkdir(parents=True, exist_ok=True)

        timeline = self.domain_timeline(domain)
        if not timeline:
            return od, od

        csv_rows = ["run_id,timestamp,passed,failed,pass_rate"]
        for t in timeline:
            csv_rows.append(
                f"{t['run_id']},{t['timestamp']},{t['passed']},{t['failed']},{t['pass_rate']}"
            )
        csv_path = od / f"{domain.replace('@', '').replace('/', '_')}_timeline.csv"
        csv_path.write_text("\n".join(csv_rows))

        md_lines = [
            f"# {domain} — Experiment Timeline",
            "",
            "| Run | Date | Passed | Failed | Rate |",
            "|-----|------|--------|--------|------|",
        ]
        for t in timeline:
            ts = t["timestamp"][:10]
            md_lines.append(
                f"| {t['run_id']} | {ts} | {t['passed']} | {t['failed']} | {t['pass_rate']}% |"
            )
        md_path = od / f"{domain.replace('@', '').replace('/', '_')}_timeline.md"
        md_path.write_text("\n".join(md_lines))

        return csv_path, md_path

    # ---- Maintenance ----

    def stats(self) -> Dict:
        """Return overall evidence store statistics."""
        runs = list(self.runs_dir.iterdir())
        run_count = sum(1 for r in runs if r.is_dir() and (r / "run.json").exists())

        domain_count = 0
        for d in self.domains_dir.iterdir():
            if d.is_dir() and (d / "timeline.json").exists():
                domain_count += 1

        total_size = sum(
            f.stat().st_size
            for f in self.root.rglob("*")
            if f.is_file()
        )

        return {
            "total_runs": run_count,
            "domains_tracked": domain_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
        }


# ---- CLI ----

def evidence_store_cli():
    import argparse
    from kdna_lab.paths import LAB_ROOT

    parser = argparse.ArgumentParser(description="KDNA Lab Evidence Store")
    parser.add_argument("--dir", default=str(LAB_ROOT / "evidence"),
                        help="Evidence store directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="Show evidence store statistics")
    list_p = sub.add_parser("list", help="List archived runs")
    list_p.add_argument("--type", help="Filter by run type")
    list_p.add_argument("--target", help="Filter by target")
    list_p.add_argument("--limit", type=int, default=20)

    show_p = sub.add_parser("show", help="Show run details")
    show_p.add_argument("run_id")

    timeline_p = sub.add_parser("timeline", help="Show domain timeline")
    timeline_p.add_argument("domain")

    compare_p = sub.add_parser("compare", help="Compare two runs")
    compare_p.add_argument("run_1")
    compare_p.add_argument("run_2")

    export_p = sub.add_parser("export", help="Export paper data")
    export_p.add_argument("domain")

    args = parser.parse_args()
    store = EvidenceStore(Path(args.dir))

    if args.command == "stats":
        s = store.stats()
        print(f"\nEvidence Store: {args.dir}")
        print(f"  Runs: {s['total_runs']}")
        print(f"  Domains tracked: {s['domains_tracked']}")
        print(f"  Size: {s['total_size_mb']} MB")

    elif args.command == "list":
        runs = store.list_runs(run_type=args.type, target=args.target, limit=args.limit)
        if not runs:
            print("No runs archived yet.")
        else:
            print(f"\n{'Run ID':<30} {'Type':<14} {'Target':<30} {'Rate':>6} {'Date'}")
            print("-" * 100)
            for r in runs:
                print(f"{r['run_id']:<30} {r.get('type',''):<14} {r.get('target',''):<30} {r.get('pass_rate',0):>4}%  {r['timestamp'][:10]}")

    elif args.command == "show":
        run = store.get_run(args.run_id)
        if run:
            res = run.pop("results", None)
            print(json.dumps(run, indent=2, ensure_ascii=False))
            if res:
                print(f"\n# {len(res)} results (use --json for full output)")
        else:
            print(f"Run not found: {args.run_id}")

    elif args.command == "timeline":
        timeline = store.domain_timeline(args.domain)
        if not timeline:
            print(f"No data for {args.domain}")
        else:
            for t in timeline:
                print(f"  {t['run_id']}  {t['timestamp'][:10]}  {t['pass_rate']}%  ({t['passed']}/{t['passed'] + t['failed']})")

    elif args.command == "compare":
        diff = store.compare_runs(args.run_1, args.run_2)
        if "error" in diff:
            print(f"[ERROR] {diff['error']}")
        else:
            print(f"\nRun comparison: {args.run_1} vs {args.run_2}")
            print(f"  Pass rate: {diff['pass_rate_1']}% → {diff['pass_rate_2']}%  (Δ{'+' if diff['delta'] > 0 else ''}{diff['delta']}%)")
            print(f"  Improved: {len(diff['improved'])}")
            print(f"  Regressed: {len(diff['regressed'])}")
            print(f"  Unchanged (pass): {diff['unchanged_pass']}")
            print(f"  Unchanged (fail): {diff['unchanged_fail']}")

    elif args.command == "export":
        csv_p, md_p = store.export_paper_data(args.domain)
        print(f"CSV -> {csv_p}")
        print(f"MD  -> {md_p}")

    else:
        parser.print_help()


if __name__ == "__main__":
    evidence_store_cli()
