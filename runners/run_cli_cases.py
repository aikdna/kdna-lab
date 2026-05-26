#!/usr/bin/env python3
"""
KDNA Lab — CLI Case Runner

Reads CLI test cases from JSONL and executes kdna CLI commands,
collecting exit codes, stdout, stderr.

Modes:
  --plan    Generate execution scripts (default)
  --run     Execute CLI commands directly
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

LAB_ROOT = Path(__file__).resolve().parent.parent

def load_config():
    config_path = LAB_ROOT / "configs" / "default.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"output": {"dir": str(LAB_ROOT / "outputs")}, "runners": {"cli": {"timeout": 30}}}

def load_cases(case_file):
    cases = []
    with open(case_file) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases

def resolve_output_dir(config):
    output_dir = config.get("output", {}).get("dir", "outputs")
    if not os.path.isabs(output_dir):
        output_dir = str(LAB_ROOT / output_dir)
    return output_dir

def run_cli_command(command, timeout=30, env=None):
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, env=env or os.environ
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": True
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "success": False
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }

def substitute_fixture(command, fixtures_dir):
    """Replace 'fixture:' references with actual paths"""
    if "fixture:" in command:
        parts = command.split()
        for i, part in enumerate(parts):
            if part.startswith("fixture:"):
                fixture_name = part.replace("fixture:", "")
                fixture_path = Path(fixtures_dir) / fixture_name
                if fixture_path.exists():
                    parts[i] = str(fixture_path)
    return " ".join(parts)

def run_plan_mode(cases, config):
    output_dir = resolve_output_dir(config)
    plans = []

    for case in cases:
        command = case.get("input", "")
        plan = {
            "case_id": case["id"],
            "category": case.get("category", ""),
            "command": command,
            "expected_exit_code": case.get("expected_exit_code", 0),
            "expected_behavior": case.get("expected_behavior", "comply"),
            "must_include": case.get("must_include", []),
            "must_not_include": case.get("must_not_include", [])
        }
        plans.append(plan)

    plan_path = Path(output_dir) / "cli_run_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)

    print(f"[PLAN] Generated {len(plans)} CLI test plans → {plan_path}")
    print(f"\n[PLAN] To execute manually:")
    print(f"  1. Run each command and save outputs to outputs/raw/")
    print(f"  2. Run: python runners/run_cli_cases.py --run")
    print(f"  3. Run: python scorers/rule_scorer.py (reads both .txt and .json outputs)")

    return plans

def run_execute_mode(cases, config):
    output_dir = resolve_output_dir(config)
    raw_dir = Path(output_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    fixtures_dir = LAB_ROOT / "fixtures"
    timeout = config.get("runners", {}).get("cli", {}).get("timeout", 30)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    results = []

    for i, case in enumerate(cases):
        command = substitute_fixture(case.get("input", ""), fixtures_dir)
        print(f"[EXEC] ({i+1}/{len(cases)}) {case['id']} ... ", end="", flush=True)

        output = run_cli_command(command, timeout=timeout)

        result = {
            "run_id": run_id,
            "case_id": case["id"],
            "command": command,
            "exit_code": output["exit_code"],
            "stdout": output["stdout"][:5000],
            "stderr": output["stderr"][:2000],
            "expected_exit_code": case.get("expected_exit_code", 0),
            "success": output["success"]
        }
        results.append(result)

        # Save raw output
        outpath = raw_dir / f"{run_id}_{case['id']}.json"
        with open(outpath, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        exit_ok = output["exit_code"] == case.get("expected_exit_code", 0)
        status = "OK" if exit_ok else f"EXIT={output['exit_code']}"
        print(status)

    # Save run index
    index_path = Path(output_dir) / f"{run_id}_cli_index.json"
    with open(index_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    passed = sum(1 for r in results if r["exit_code"] == r["expected_exit_code"])
    print(f"\n[EXEC] Done. {passed}/{len(results)} passed exit code checks.")
    print(f"[EXEC] Results → {index_path}")

    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab CLI Case Runner")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Generate run plan (default if no --run)")
    parser.add_argument("--run", action="store_true", help="Execute CLI commands")
    parser.add_argument("--config", default=None, help="Config file path")
    args = parser.parse_args()

    config = load_config()
    if args.config:
        import yaml
        with open(args.config) as f:
            config = yaml.safe_load(f)

    # Resolve output dir
    output_dir = config.get("output", {}).get("dir", "outputs")
    if not os.path.isabs(output_dir):
        output_dir = str(LAB_ROOT / output_dir)
    config.setdefault("output", {})["dir"] = output_dir

    case_file = args.case_file or str(LAB_ROOT / "examples" / "cli" / "cases.jsonl")
    cases = load_cases(case_file)
    print(f"[INFO] Loaded {len(cases)} CLI cases from {case_file}")

    if args.run:
        run_execute_mode(cases, config)
    else:
        run_plan_mode(cases, config)

if __name__ == "__main__":
    main()
