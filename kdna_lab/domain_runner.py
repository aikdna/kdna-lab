"""KDNA Lab — Domain Case Runner.

Reads domain test cases from JSONL, loads the KDNA domain,
and runs experiments via LLM API or generates execution plans.
"""

import json
import hashlib
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from kdna_lab.cases import load_cases_list
from kdna_lab.config import load_config, resolve_output_dir
from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner


BEST_PROMPT_TEMPLATE = """You are a careful, precise technical communicator for KDNA (Knowledge DNA).

KDNA is an open judgment protocol — not a prompt library, not a RAG system, not a workflow tool.
It packages domain-specific judgment structures that AI agents can load, trace, and evolve.

When writing about KDNA:
1. Distinguish KDNA from prompts, RAG, skills, and workflows.
2. Never claim KDNA guarantees correctness — it provides inspectability.
3. Always include boundaries: what KDNA is NOT, what it can NOT do.
4. Never fabricate data — ask for source materials when needed.
5. Keep claims grounded and verifiable.

Respond to the following task with these principles in mind."""


class DomainRunner(ExperimentRunner):
    """Run domain behavior experiments."""

    BEST_PROMPT_CONDITIONS = {"best_prompt"}

    def _api_metadata(self) -> dict:
        api = self.config.get("api", {})
        return {
            "provider": api.get("provider", "openai"),
            "model": api.get("model", "gpt-4o"),
            "base_url": api.get("base_url"),
        }

    def _load_domain_metadata(self, domain: str) -> dict:
        try:
            result = subprocess.run(
                ["kdna", "load", domain, "--as=json"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return {}
            payload = json.loads(result.stdout)
            manifest = payload.get("manifest", {})
            trust = payload.get("trust", {})
            return {
                "domain_version": manifest.get("version"),
                "asset_digest": trust.get("asset_digest") or manifest.get("asset_digest"),
                "content_digest": trust.get("content_digest") or manifest.get("content_digest"),
            }
        except Exception:
            return {}

    def _input_hash(self, text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _write_benchmark_run_artifact(
        self,
        domain: str,
        domain_meta: dict,
        results: List[dict],
        executed_case_count: int,
    ) -> str:
        api_meta = self._api_metadata()
        artifact = {
            "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
            "run_id": self.run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "domain": domain,
            "domain_version": domain_meta.get("domain_version"),
            "asset_digest": domain_meta.get("asset_digest"),
            "content_digest": domain_meta.get("content_digest"),
            "provider": api_meta["provider"],
            "model": api_meta["model"],
            "base_url": api_meta.get("base_url"),
            "conditions": sorted({r.get("condition", "") for r in results if r.get("condition")}),
            "case_count": executed_case_count,
            "cases": [
                {
                    "case_id": r["case_id"],
                    "condition": r.get("condition"),
                    "input_hash": self._input_hash(r.get("case", {}).get("input", "")),
                    "output_path": r.get("output_path"),
                    "output": r.get("output", ""),
                    "scores": {},
                    "pass": None,
                    "error": r.get("error"),
                    "timestamp": r.get("timestamp"),
                }
                for r in results
            ],
            "status": "raw",
        }
        path = self.raw_dir / f"{self.run_id}_benchmark-run-v1.raw.json"
        path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
        return str(path)

    def _build_prompt(self, domain_prompt: str, condition: str, case: dict) -> str:
        if condition == "no_kdna":
            return case["input"]
        if condition in self.BEST_PROMPT_CONDITIONS:
            return f"{BEST_PROMPT_TEMPLATE}\n\n[USER INPUT]\n{case['input']}"
        parts = [domain_prompt, "\n---\n"]
        parts.append("Apply silently. Do not quote KDNA to the user.\n")
        parts.append(f"\n[USER INPUT]\n{case['input']}\n")
        return "".join(parts)

    def run_all(self, cases: List[dict]) -> List[dict]:
        domain = self.config.get("domain", {}).get("name", "@aikdna/kdna_propagation")
        domain_prompt = self.load_domain_prompt(domain)
        if domain_prompt is None:
            raise RuntimeError(f"Failed to load domain: {domain}")
        domain_meta = self._load_domain_metadata(domain)
        api_meta = self._api_metadata()

        results = []
        rate_limit = self.config.get("runners", {}).get("domain", {}).get("rate_limit", 0.5)

        for i, case in enumerate(cases):
            conditions = case.get("conditions", ["kdna_full"])
            for condition in conditions:
                prompt = self._build_prompt(domain_prompt, condition, case)
                print(f"  [{i+1}/{len(cases)}] {case['id']} [{condition}] ... ", end="", flush=True)
                output = self.call_api(prompt)

                if output is None:
                    print("FAILED")
                    continue

                outpath = self.save_output(
                    case["id"], output,
                    _ext="txt",
                    Run=self.run_id,
                    Condition=condition,
                    Provider=api_meta["provider"],
                    Model=api_meta["model"],
                    Domain=domain,
                )
                results.append({
                    "run_id": self.run_id,
                    "case_id": case["id"],
                    "condition": condition,
                    "output_path": outpath,
                    "output": output,
                    "case": case,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
                print(f"{len(output)} chars")
                time.sleep(rate_limit)

        self.save_index(results)
        artifact_path = self._write_benchmark_run_artifact(domain, domain_meta, results, len(cases))
        print(f"[ARTIFACT] benchmark-run-v1 raw -> {artifact_path}")
        return results

    def run_plan(self, cases: List[dict]) -> List[dict]:
        """Generate execution prompts without calling the API."""
        domain = self.config.get("domain", {}).get("name", "@aikdna/kdna_propagation")
        domain_prompt = self.load_domain_prompt(domain)
        if domain_prompt is None:
            raise RuntimeError(f"Failed to load domain: {domain}")

        plans = []
        for case in cases:
            conditions = case.get("conditions", ["kdna_full"])
            for condition in conditions:
                prompt = self._build_prompt(domain_prompt, condition, case)
                plan = {
                    "run_id": self.run_id,
                    "case_id": case["id"],
                    "condition": condition,
                    "domain": domain,
                    "area": case.get("area", case.get("category", "")),
                    "input": case["input"],
                    "expected_behavior": case.get("expected_behavior", ""),
                    "prompt": prompt,
                    "must_include": case.get("must_include", []),
                    "must_not_include": case.get("must_not_include", []),
                    "rubric": case.get("rubric", {}),
                }
                plans.append(plan)

                prompt_path = self.output_dir / "raw" / f"{self.run_id}_{case['id']}_{condition}_prompt.txt"
                prompt_path.parent.mkdir(parents=True, exist_ok=True)
                prompt_path.write_text(prompt)

        plan_path = self.output_dir / "run_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)

        print(f"[PLAN] {len(plans)} test plans → {plan_path}")
        return plans


def run_domain_cases(
    case_file: str | None = None,
    config_path: str | None = None,
    domain: str | None = None,
    execute: bool = False,
) -> List[dict]:
    """Main entry point for domain case experiments.

    Args:
        case_file: Path to JSONL case file (defaults to examples/kdna_propagation/cases.jsonl)
        config_path: Path to YAML config file
        domain: Domain name override
        execute: If True, call LLM API; if False, generate plan only
    """
    cfg = load_config(LAB_ROOT, Path(config_path) if config_path else None)
    cfg["output"]["dir"] = resolve_output_dir(cfg, LAB_ROOT)

    if domain:
        cfg.setdefault("domain", {})["name"] = domain

    cf = case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    cases = load_cases_list(cf)
    print(f"[INFO] Loaded {len(cases)} cases from {cf}")

    runner = DomainRunner(LAB_ROOT, cfg)

    if execute:
        results = runner.run_all(cases)
        print(f"[EXEC] Done. {len(results)} outputs saved.")
        print(f"[EXEC] Outputs → {runner.output_dir}/raw/")
        return results
    else:
        runner.run_plan(cases)
        return []


def run_domain_cases_cli():
    """CLI entry point for domain runner."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Domain Case Runner")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Generate run plan (default if no --execute)")
    parser.add_argument("--execute", action="store_true", help="Execute via LLM API")
    parser.add_argument("--domain", help="Domain name override")
    parser.add_argument("--config", default=None, help="Config file path")
    args = parser.parse_args()

    run_domain_cases(
        case_file=args.case_file,
        config_path=args.config,
        domain=args.domain,
        execute=args.execute,
    )
