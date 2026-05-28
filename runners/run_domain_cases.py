#!/usr/bin/env python3
"""
KDNA Lab — Domain Case Runner

Reads domain test cases from JSONL, loads the KDNA domain,
generates run plans and/or executes via LLM API.

Modes:
  --plan       Generate execution prompts (default, for manual agent execution)
  --execute    Run via configured LLM API
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

LAB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_ROOT))

from lib.cases import load_cases_list
from lib.config import load_config, resolve_output_dir


def load_domain_prompt(domain_name):
    result = subprocess.run(
        ["kdna", "load", domain_name, "--as=prompt"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[ERROR] Failed to load domain: {result.stderr}")
        return None
    return result.stdout


def format_prompt(domain_prompt, case):
    parts = []
    parts.append(domain_prompt)
    parts.append("\n---\n")
    parts.append("Apply silently. Do not quote KDNA to the user.\n")
    parts.append(f"\n[USER INPUT]\n{case['input']}\n")
    return "".join(parts)


def call_api(prompt, config):
    api = config["api"]
    provider = api.get("provider", "openai")
    model = api.get("model", "gpt-4o")
    api_key = os.environ.get(api.get("api_key_env", "OPENAI_API_KEY"), "")
    base_url = api.get("base_url")
    temperature = api.get("temperature", 0.3)
    max_tokens = api.get("max_tokens", 4000)

    if not api_key:
        print("[ERROR] No API key found. Set environment variable or use --plan mode.")
        return None

    if provider == "openai" or base_url:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except ImportError:
            print("[ERROR] openai package not installed. Run: pip install openai")
            return None
        except Exception as e:
            print(f"[ERROR] API call failed: {e}")
            return None

    print(f"[ERROR] Unsupported provider: {provider}")
    return None


def save_output(run_id, case_id, condition, output, config):
    output_dir = Path(config["output"]["dir"]) / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{run_id}_{case_id}.txt"
    with open(filepath, "w") as f:
        f.write(f"# Run: {run_id}\n")
        f.write(f"# Case: {case_id}\n")
        f.write(f"# Condition: {condition}\n")
        f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
        f.write("---\n")
        f.write(output)
    return str(filepath)


def save_run_plan(plans, config):
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "run_plan.json"
    with open(filepath, "w") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)
    return str(filepath)


def run_plan_mode(cases, config):
    domain = config.get("domain", {}).get("name")
    if not domain:
        print("[ERROR] No domain configured. Set domain.name in configs/default.yaml")
        return

    domain_prompt = load_domain_prompt(domain)
    if domain_prompt is None:
        return

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    plans = []

    for case in cases:
        conditions = case.get("conditions", ["kdna_full"])
        for condition in conditions:
            plan = {
                "run_id": run_id,
                "case_id": case["id"],
                "condition": condition,
                "domain": domain,
                "area": case.get("area", case.get("category", "")),
                "category": case.get("category", ""),
                "input": case["input"],
                "expected_behavior": case.get("expected_behavior", ""),
                "prompt": format_prompt(domain_prompt if condition != "no_kdna" else "", case),
                "must_include": case.get("must_include", []),
                "must_not_include": case.get("must_not_include", []),
                "rubric": case.get("rubric", {})
            }
            plans.append(plan)

            prompt_file = Path(config["output"]["dir"]) / "raw" / f"{run_id}_{case['id']}_prompt.txt"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompt_file, "w") as f:
                f.write(plan["prompt"])

    plan_path = save_run_plan(plans, config)
    print(f"[PLAN] Generated {len(plans)} test plans → {plan_path}")
    print(f"[PLAN] Prompt files saved to outputs/raw/")
    print(f"\n[PLAN] To execute manually:")
    print(f"  1. Load domain: kdna load {domain}")
    print(f"  2. For each case, read the prompt file and respond")
    print(f"  3. Save outputs to outputs/raw/{{run_id}}_{{case_id}}.txt")
    print(f"  4. Run: python scorers/rule_scorer.py")

    return plans


def run_execute_mode(cases, config):
    domain = config.get("domain", {}).get("name")
    if not domain:
        print("[ERROR] No domain configured.")
        return

    domain_prompt = load_domain_prompt(domain)
    if domain_prompt is None:
        return

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    results = []

    for i, case in enumerate(cases):
        conditions = case.get("conditions", ["kdna_full"])
        for condition in conditions:
            if condition == "no_kdna":
                prompt = case["input"]
            else:
                prompt = format_prompt(domain_prompt, case)

            print(f"[EXEC] ({i+1}/{len(cases)}) {case['id']} [{condition}] ...", end=" ", flush=True)
            output = call_api(prompt, config)

            if output is None:
                print("FAILED (API)")
                continue

            outpath = save_output(run_id, case["id"], condition, output, config)
            results.append({
                "run_id": run_id,
                "case_id": case["id"],
                "condition": condition,
                "output_path": outpath,
                "case": case
            })
            print(f"OK ({len(output)} chars)")

            time.sleep(config.get("runners", {}).get("domain", {}).get("rate_limit", 0.5))

    index_path = Path(config["output"]["dir"]) / f"{run_id}_index.json"
    with open(index_path, "w") as f:
        json.dump([{
            "run_id": r["run_id"],
            "case_id": r["case_id"],
            "condition": r["condition"],
            "output_path": r["output_path"]
        } for r in results], f, indent=2)

    print(f"\n[EXEC] Done. {len(results)}/{len(cases) * len(conditions)} cases completed.")
    print(f"[EXEC] Outputs → {config['output']['dir']}/raw/")
    print(f"[EXEC] Run scorer: python scorers/rule_scorer.py")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Domain Case Runner")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Generate run plan (default if no --execute)")
    parser.add_argument("--execute", action="store_true", help="Execute via LLM API")
    parser.add_argument("--domain", help="Domain name override")
    parser.add_argument("--config", default=None, help="Config file path")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    config = load_config(LAB_ROOT, config_path)
    config["output"]["dir"] = resolve_output_dir(config, LAB_ROOT)

    if args.domain:
        config.setdefault("domain", {})["name"] = args.domain

    case_file = args.case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    cases = load_cases_list(case_file)
    print(f"[INFO] Loaded {len(cases)} cases from {case_file}")

    if args.execute:
        run_execute_mode(cases, config)
    else:
        run_plan_mode(cases, config)


if __name__ == "__main__":
    main()
