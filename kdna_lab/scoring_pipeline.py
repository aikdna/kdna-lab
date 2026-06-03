"""KDNA Lab — Scoring Pipeline.

Orchestrates the multi-layer scoring flow:
  L1 (Hard Checks) → L2 (LLM Judge) → L3 (Human Audit)

Each layer feeds into the next. L3 results are tracked for human review.
Integrates with Evidence Store for archival.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from kdna_lab.cases import load_cases
from kdna_lab.outputs import find_outputs, extract_output_body
from kdna_lab.rule_scorer import score_case as l1_score_case
from kdna_lab.report import generate_l1_report, generate_domain_report
from kdna_lab.paths import LAB_ROOT
from kdna_lab.evidence_store import EvidenceStore


# L2 Judge callback signature:
#   judge_fn(case: dict, output_body: str, config: dict) -> dict
# Returns: {"scores": {...}, "total": int, "max_total": int, "passed": bool, "summary": str}
L2JudgeFn = Callable[[Dict, str, Dict], Dict]


class ScoringPipeline:
    """Multi-layer scoring pipeline: L1 → L2 → L3.

    Usage:
        pipeline = ScoringPipeline(lab_root)
        pipeline.run(case_file, output_dir)
        # Optional L2:
        pipeline.run(case_file, output_dir, l2_judge=my_llm_judge_fn)
    """

    def __init__(self, lab_root: Path, config: Optional[Dict] = None):
        self.lab_root = lab_root
        self.config = config or {}
        self.store = EvidenceStore(lab_root / "evidence")

    def run(
        self,
        case_file: str,
        output_dir: str,
        l2_judge: Optional[L2JudgeFn] = None,
        l2_config: Optional[Dict] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the full scoring pipeline.

        Returns a dict with L1, L2 (if judge provided), and L3 scaffolding.
        """
        run_id = run_id or datetime.now().strftime("pipeline_%Y%m%d_%H%M%S")
        cases = load_cases(case_file)
        outputs = find_outputs(output_dir)

        l1_results = self._run_l1(cases, outputs)
        l2_results = None
        if l2_judge:
            l2_results = self._run_l2(l1_results, l2_judge, l2_config or {})

        combined = self._combine_results(l1_results, l2_results)

        pipeline_result = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "case_file": case_file,
            "total_cases": len(cases),
            "matched_outputs": len(l1_results),
            "L1": self._l1_summary(l1_results),
            "L2": self._l2_summary(l2_results) if l2_results else None,
            "L3": {"reviewed": 0, "pending": len(l1_results)},
            "results": combined,
        }

        # Save combined results
        out_path = Path(output_dir) / f"{run_id}_combined_scores.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(pipeline_result, f, indent=2, ensure_ascii=False)

        benchmark_path = self._write_benchmark_run_artifact(pipeline_result, case_file, output_dir)
        pipeline_result["benchmark_run_artifact"] = benchmark_path

        # Archive to evidence store
        self._archive(pipeline_result)

        return pipeline_result

    def _run_l1(self, cases: Dict, outputs: Dict) -> List[Dict]:
        """Run L1 hard checks on all matched outputs."""
        results = []
        for case_id, case in cases.items():
            if case_id not in outputs:
                continue
            for output_info in outputs[case_id]:
                body = extract_output_body(output_info["content"])
                score = l1_score_case(case, body)
                results.append({
                    "case_id": case_id,
                    "condition": output_info.get("condition"),
                    "output_file": output_info["file"],
                    "output_type": output_info.get("type", "domain"),
                    "output_body": body,
                    "error": output_info.get("error"),
                    "score": score,
                    "L1_pass": score["L1"]["passed"],
                    "case": case,
                })
        return results

    def _run_l2(
        self, l1_results: List[Dict], judge_fn: L2JudgeFn, config: Dict
    ) -> List[Dict]:
        """Run L2 LLM judge on L1 results. Skips cases with provider errors/timeouts."""
        results = []
        skipped = 0
        for r in l1_results:
            if r.get("error"):
                results.append({
                    "case_id": r["case_id"],
                    "condition": r.get("condition"),
                    "L2": {
                        "status": "not_run",
                        "reason": r.get("error", "unknown_error"),
                        "passed": False,
                        "scores": {},
                        "total": 0,
                        "max_total": 0,
                    },
                })
                skipped += 1
                continue
            try:
                l2 = judge_fn(r["case"], r["output_body"], config)
            except Exception as e:
                l2 = {"error": str(e), "scores": {}, "total": 0, "max_total": 0, "passed": False}
            results.append({
                "case_id": r["case_id"],
                "condition": r.get("condition"),
                "L2": l2,
            })
        if skipped > 0:
            print(f"[L2] Skipped {skipped} cases with provider errors (L2 not_run)")
        return results

    def _combine_results(
        self, l1_results: List[Dict], l2_results: Optional[List[Dict]]
    ) -> List[Dict]:
        """Combine L1 and L2 results into unified per-case records."""
        l2_map = {}
        if l2_results:
            l2_map = {(r["case_id"], r.get("condition")): r["L2"] for r in l2_results}

        combined = []
        for r in l1_results:
            l2_score = l2_map.get((r["case_id"], r.get("condition")), {})
            l2_pass = None
            if l2_score:
                if l2_score.get("status") != "not_run":
                    l2_pass = l2_score.get("passed")
            combined.append({
                "case_id": r["case_id"],
                "condition": r.get("condition"),
                "output_file": r["output_file"],
                "output_body": r.get("output_body", ""),
                "error": r.get("error"),
                "L1_pass": r["L1_pass"],
                "L1_score": r["score"],
                "L2_pass": l2_pass,
                "L2_score": l2_score,
                "L3_status": "pending",
                "L3_reviewer": None,
                "L3_verdict": None,
                "L3_notes": None,
            })
        return combined

    def _write_benchmark_run_artifact(
        self,
        pipeline_result: Dict[str, Any],
        case_file: str,
        output_dir: str,
    ) -> str:
        """Write scored benchmark-run-v1 JSON for public evidence export.

        Inherits provider, model, domain_version, asset_digest, content_digest,
        and input_hash from the raw benchmark artifact when available.
        """
        cases = load_cases(case_file)
        results = pipeline_result.get("results", [])
        domain = None
        for case in cases.values():
            domain = case.get("target") or case.get("domain")
            if domain:
                break

        raw_meta = self._load_raw_artifact_metadata(output_dir)

        artifact = {
            "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
            "run_id": pipeline_result["run_id"],
            "created_at": pipeline_result["timestamp"],
            "domain": domain,
            "domain_version": raw_meta.get("domain_version"),
            "asset_digest": raw_meta.get("asset_digest"),
            "content_digest": raw_meta.get("content_digest"),
            "provider": raw_meta.get("provider", "unknown"),
            "model": raw_meta.get("model", "unknown"),
            "base_url": raw_meta.get("base_url"),
            "conditions": sorted({r.get("condition") for r in results if r.get("condition")}),
            "case_count": len(cases),
            "case_file": case_file,
            "cases": [],
            "status": "scored",
        }

        case_count = raw_meta.get("case_count") or len(cases)
        raw_input_hashes = raw_meta.get("input_hashes", {})

        for r in results:
            case = cases.get(r["case_id"], {})
            output = r.get("output_body", "")
            input_hash = raw_input_hashes.get(
                r.get("case_id"),
                r.get("input_hash"),
            )
            scores = {"L1": r.get("L1_score", {}).get("L1", {})}
            if r.get("L2_score"):
                l2_score = r["L2_score"]
                scores["L2"] = {
                    "status": l2_score.get("status", "scored"),
                    "passed": l2_score.get("passed"),
                    "scores": l2_score.get("scores", {}),
                    "total": l2_score.get("total"),
                    "max_total": l2_score.get("max_total"),
                    "summary": l2_score.get("summary"),
                    "error": l2_score.get("error"),
                    "reason": l2_score.get("reason"),
                }

            pass_val = None
            l2 = r.get("L2_score", {})
            if l2:
                if l2.get("status") == "not_run":
                    pass_val = None
                elif l2.get("passed") is not None:
                    pass_val = l2["passed"]
            if pass_val is None:
                pass_val = r.get("L1_pass")

            artifact["cases"].append({
                "case_id": r["case_id"],
                "condition": r.get("condition"),
                "input_hash": input_hash,
                "output_file": r.get("output_file"),
                "output": output,
                "scores": scores,
                "pass": pass_val,
                "error": r.get("error"),
                "expected_behavior": case.get("expected_behavior"),
            })

        artifact["case_count"] = case_count

        path = Path(output_dir) / "raw" / f"{pipeline_result['run_id']}_benchmark-run-v1.scored.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
        return str(path)

    def _load_raw_artifact_metadata(self, output_dir: str) -> Dict[str, Any]:
        """Load metadata from the latest raw benchmark artifact for scored artifact inheritance."""
        raw_dir = Path(output_dir) / "raw"
        if not raw_dir.exists():
            return {}

        raw_files = []
        for f in raw_dir.glob("*_benchmark-run-v1.raw.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("schema") == "https://aikdna.com/schemas/benchmark-run-v1.json":
                    raw_files.append(f)
            except json.JSONDecodeError:
                continue

        if not raw_files:
            return {}

        latest = max(raw_files, key=lambda path: path.stat().st_mtime)
        try:
            data = json.loads(latest.read_text())
        except json.JSONDecodeError:
            return {}

        input_hashes = {}
        for c in data.get("cases", []):
            if isinstance(c, dict) and c.get("case_id") and c.get("input_hash"):
                input_hashes[c["case_id"]] = c["input_hash"]

        return {
            "provider": data.get("provider"),
            "model": data.get("model"),
            "base_url": data.get("base_url"),
            "domain_version": data.get("domain_version"),
            "asset_digest": data.get("asset_digest"),
            "content_digest": data.get("content_digest"),
            "case_count": data.get("case_count"),
            "conditions": data.get("conditions", []),
            "input_hashes": input_hashes,
        }

    def _l1_summary(self, results: List[Dict]) -> Dict:
        total = len(results)
        passed = sum(1 for r in results if r["L1_pass"])
        return {"total": total, "passed": passed, "failed": total - passed,
                "pass_rate": round(passed / total * 100) if total else 0}

    def _l2_summary(self, results: List[Dict]) -> Dict:
        if not results:
            return {"total": 0, "passed": 0, "failed": 0, "not_run": 0, "pass_rate": 0}
        total = len(results)
        passed = sum(1 for r in results
                     if r.get("L2", {}).get("status") != "not_run"
                     and r.get("L2", {}).get("passed", False))
        failed = sum(1 for r in results
                     if r.get("L2", {}).get("status") != "not_run"
                     and not r.get("L2", {}).get("passed", True)
                     and r.get("L2", {}).get("scores"))
        not_run = sum(1 for r in results if r.get("L2", {}).get("status") == "not_run")
        scored_total = total - not_run
        scores = [
            r.get("L2", {}).get("total", 0)
            for r in results
            if r.get("L2", {}).get("status") != "not_run"
            and r.get("L2", {}).get("total") is not None
        ]
        return {
            "total": total,
            "scored": scored_total,
            "passed": passed,
            "failed": failed,
            "not_run": not_run,
            "pass_rate": round(passed / scored_total * 100) if scored_total else 0,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        }

    def _archive(self, result: Dict):
        """Archive pipeline result to evidence store."""
        try:
            self.store.ingest_run(
                run_id=result["run_id"],
                run_type="pipeline",
                target="scoring_pipeline",
                results=result["results"],
            )
        except Exception:
            pass


# ---- Human Review (L3) Tracking ----

def record_human_review(
    combined_scores_file: str,
    case_id: str,
    reviewer: str,
    verdict: str,
    notes: str = "",
) -> Dict:
    """Record a human review verdict for a specific case.

    Args:
        combined_scores_file: Path to pipeline JSON output
        case_id: Case to review
        reviewer: Name/ID of human reviewer
        verdict: 'pass', 'fail', or 'needs_discussion'
        notes: Review notes
    """
    data = json.loads(Path(combined_scores_file).read_text())
    results = data.get("results", [])

    for r in results:
        if r["case_id"] == case_id:
            r["L3_status"] = "reviewed"
            r["L3_reviewer"] = reviewer
            r["L3_verdict"] = verdict
            r["L3_notes"] = notes
            break

    data["L3"]["reviewed"] = sum(1 for r in results if r.get("L3_status") == "reviewed")
    data["L3"]["pending"] = len(results) - data["L3"]["reviewed"]

    Path(combined_scores_file).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def generate_pipeline_report(pipeline_result: Dict, output_path: str) -> str:
    """Generate a comprehensive L1+L2+L3 pipeline report."""
    lines = []
    lines.append("# KDNA Lab — Scoring Pipeline Report")
    lines.append("")
    lines.append(f"**Run ID:** {pipeline_result['run_id']}")
    lines.append(f"**Date:** {pipeline_result['timestamp'][:19]}")
    lines.append(f"**Cases:** {pipeline_result['total_cases']} total, {pipeline_result['matched_outputs']} matched")
    lines.append("")

    lines.append("## L1 — Hard Checks")
    l1 = pipeline_result["L1"]
    lines.append(f"- Passed: {l1['passed']}/{l1['total']} ({l1['pass_rate']}%)")
    lines.append(f"- Failed: {l1['failed']}")
    lines.append("")

    if pipeline_result.get("L2"):
        lines.append("## L2 — LLM Judge")
        l2 = pipeline_result["L2"]
        lines.append(f"- Passed: {l2['passed']}/{l2['total']} ({l2['pass_rate']}%)")
        lines.append(f"- Avg Score: {l2['avg_score']}")
        lines.append("")

    lines.append("## L3 — Human Review")
    l3 = pipeline_result["L3"]
    lines.append(f"- Reviewed: {l3['reviewed']}")
    lines.append(f"- Pending: {l3['pending']}")
    lines.append("")

    lines.append("## Detailed Results")
    lines.append("| Case | L1 | L2 | L3 Status | L3 Verdict |")
    lines.append("|------|-----|-----|-----------|------------|")
    for r in pipeline_result["results"]:
        l1_s = "PASS" if r["L1_pass"] else "FAIL"
        l2_s = "PASS" if r.get("L2_pass") else ("FAIL" if r.get("L2_pass") is False else "—")
        l3_status = r.get("L3_status", "pending")
        l3_verdict = r.get("L3_verdict", "—") or "—"
        lines.append(f"| {r['case_id']} | {l1_s} | {l2_s} | {l3_status} | {l3_verdict} |")
    lines.append("")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def pipeline_cli():
    """CLI entry point for scoring pipeline."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Scoring Pipeline")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run scoring pipeline")
    run_p.add_argument("--case-file", default=None)
    run_p.add_argument("--output-dir", default=None)
    run_p.add_argument("--l2", action="store_true", help="Run L2 LLM judge (requires API key)")

    review_p = sub.add_parser("review", help="Record human review verdict")
    review_p.add_argument("scores_file", help="Pipeline scores JSON")
    review_p.add_argument("case_id")
    review_p.add_argument("--verdict", choices=["pass", "fail", "needs_discussion"], required=True)
    review_p.add_argument("--reviewer", default="human")
    review_p.add_argument("--notes", default="")

    report_p = sub.add_parser("report", help="Generate pipeline report")
    report_p.add_argument("scores_file", help="Pipeline scores JSON")

    args = parser.parse_args()
    pipeline = ScoringPipeline(LAB_ROOT)

    if args.command == "run":
        cf = args.case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
        od = args.output_dir or str(LAB_ROOT / "outputs")

        l2_judge = None
        if args.l2:
            try:
                from internal_lib.llm_client import call_llm
                from internal_lib.config import load_config as load_int_config
                int_cfg = load_int_config(LAB_ROOT)

                def l2_fn(case, body, cfg):
                    from kdna_lab_internal_scorers_llm_judge import score_case as internal_score
                    return internal_score(case, body, cfg)

                l2_judge = l2_fn
                print("[INFO] L2 judge loaded from kdna-lab-internal")
            except ImportError:
                print("[WARN] kdna-lab-internal not available. L2 requires internal_lib.llm_client.")
                print("[INFO] Running L1 only.")
                l2_judge = None

        result = pipeline.run(cf, od, l2_judge=l2_judge)
        print(f"\n[PIPELINE] {result['run_id']}")
        print(f"  L1: {result['L1']['passed']}/{result['L1']['total']} ({result['L1']['pass_rate']}%)")
        if result.get("L2"):
            print(f"  L2: {result['L2']['passed']}/{result['L2']['total']} ({result['L2']['pass_rate']}%)")
        print(f"  L3: {result['L3']['reviewed']} reviewed, {result['L3']['pending']} pending")

    elif args.command == "review":
        result = record_human_review(
            args.scores_file, args.case_id,
            args.reviewer, args.verdict, args.notes,
        )
        print(f"[L3] {args.case_id}: {args.verdict} (by {args.reviewer})")

    elif args.command == "report":
        data = json.loads(Path(args.scores_file).read_text())
        out_path = args.scores_file.replace(".json", "_report.md")
        path = generate_pipeline_report(data, out_path)
        print(f"[REPORT] {path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    pipeline_cli()
