#!/usr/bin/env python3
"""Batch L2 scoring for completed benchmark runs across all domains."""
import os, json, sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_ROOT))

from kdna_lab.scoring_pipeline import ScoringPipeline
from kdna_lab.cases import load_cases_list

DOMAINS = ["writing", "prompt_diagnosis", "agent_safety"]

def make_l2_judge():
    """Create an L2 judge function using the local LLM provider."""
    from kdna_lab.providers import call_provider
    from kdna_lab.l2_judge import JUDGE_SYSTEM_PROMPT, build_judge_prompt, parse_judge_response

    counter = [0]

    def judge_fn(case, output_body, cfg):
        counter[0] += 1
        api_cfg = cfg.get("api", {})
        prompt = build_judge_prompt(case, output_body)
        result = call_provider(
            provider_name=api_cfg.get("provider", "openai_compatible"),
            prompt=prompt,
            model=api_cfg.get("model", "deepseek/deepseek-v4-flash"),
            system_prompt=JUDGE_SYSTEM_PROMPT,
            temperature=api_cfg.get("temperature", 0.1),
            max_tokens=1000,
            api_key=os.environ.get(api_cfg.get("api_key_env", "OPENROUTER_API_KEY"), ""),
            base_url=api_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            timeout=30,
        )
        if counter[0] % 10 == 0:
            print(f"  [L2] {counter[0]} cases judged...", flush=True)
        if result is None:
            return {"error": "Judge API call failed", "scores": {}, "total": 0, "max_total": 0, "passed": False}
        return parse_judge_response(result)

    return judge_fn

def main():
    pipeline = ScoringPipeline(LAB_ROOT)
    l2_judge = make_l2_judge()

    api_cfg = {
        "api": {
            "provider": "openai_compatible",
            "model": "deepseek/deepseek-v4-flash",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "temperature": 0.1,
            "max_tokens": 1000,
        },
        "rate_limit": 0.5,
    }

    for domain in DOMAINS:
        print(f"\n{'='*60}")
        print(f"L2 SCORING: @aikdna/{domain}")
        print(f"{'='*60}")

        case_file = str(LAB_ROOT / "examples" / domain / "cases.jsonl")
        output_dir = str(LAB_ROOT / "benchmarks" / "reference-domains" / domain / "2026-06-03")
        run_id = f"{domain}_l2_2026-06-03"

        if not Path(case_file).exists():
            print(f"SKIP: {case_file} not found")
            continue
        if not Path(output_dir).exists():
            print(f"SKIP: {output_dir} not found")
            continue

        result = pipeline.run(case_file, output_dir, l2_judge=l2_judge, l2_config=api_cfg, run_id=run_id)

        print(f"  L1: {result['L1']['passed']}/{result['L1']['total']} ({result['L1']['pass_rate']}%)")
        l2 = result.get('L2', {})
        if l2:
            print(f"  L2: {l2.get('passed',0)}/{l2.get('scored',l2.get('total',0))} ({l2.get('pass_rate',0)}%), not_run: {l2.get('not_run',0)}")
        print(f"  L3: {result['L3']['reviewed']} reviewed, {result['L3']['pending']} pending")
        print(f"  Artifact: {result['benchmark_run_artifact']}")

    print(f"\n{'='*60}")
    print("L2 scoring complete for all domains")

if __name__ == "__main__":
    main()
