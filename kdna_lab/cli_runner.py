"""KDNA Lab — CLI Case Runner.

Reads CLI test cases from JSONL and executes kdna CLI commands,
collecting exit codes, stdout, stderr.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from kdna_lab.cases import load_cases_list
from kdna_lab.config import load_config, resolve_output_dir
from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner


def run_cli_command(command: str, timeout: int = 30, env: dict | None = None) -> dict:
    """Execute a single CLI command and return structured result."""
    try:
        cmd_list = shlex.split(command)
        result = subprocess.run(
            cmd_list, capture_output=True, text=True,
            timeout=timeout, env=env or os.environ,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "success": False,
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


def substitute_fixture(command: str, fixtures_dir: Path) -> str:
    """Replace 'fixture:' references with actual paths."""
    parts = command.split()
    if "fixture:" in command:
        for i, part in enumerate(parts):
            if part.startswith("fixture:"):
                fixture_name = part.replace("fixture:", "")
                fixture_path = fixtures_dir / fixture_name
                if fixture_path.exists():
                    parts[i] = str(fixture_path)
    return " ".join(parts)


class CLIRunner(ExperimentRunner):
    """Run CLI regression experiments."""

    def run_all(self, cases: List[dict]) -> List[dict]:
        fixtures_dir = self.lab_root / "fixtures"
        timeout = self.config.get("runners", {}).get("cli", {}).get("timeout", 30)
        results = []

        for i, case in enumerate(cases):
            command = substitute_fixture(case.get("input", ""), fixtures_dir)
            print(f"  [{i+1}/{len(cases)}] {case['id']} ... ", end="", flush=True)

            output = run_cli_command(command, timeout=timeout)
            expected_exit = case.get("expected_exit_code", 0)
            exit_ok = output["exit_code"] == expected_exit

            result = {
                "run_id": self.run_id,
                "case_id": case["id"],
                "command": command,
                "exit_code": output["exit_code"],
                "stdout": output["stdout"][:5000],
                "stderr": output["stderr"][:2000],
                "expected_exit_code": expected_exit,
                "success": output["success"],
                "exit_ok": exit_ok,
            }
            results.append(result)

            outpath = self.save_output(
                case["id"],
                json.dumps(result, indent=2, ensure_ascii=False),
                _ext="json",
                Run=self.run_id,
            )
            result["output_path"] = outpath

            status = "OK" if exit_ok else f"EXIT={output['exit_code']}"
            print(status)

        self.save_index(results)
        passed = sum(1 for r in results if r["exit_ok"])
        print(f"\n[EXEC] {passed}/{len(results)} passed exit code checks.")
        return results

    def run_plan(self, cases: List[dict]) -> List[dict]:
        """Generate execution plan without running commands."""
        plans = []
        for case in cases:
            plan = {
                "case_id": case["id"],
                "area": case.get("area", case.get("category", "")),
                "command": case.get("input", ""),
                "expected_exit_code": case.get("expected_exit_code", 0),
                "expected_behavior": case.get("expected_behavior", "comply"),
                "must_include": case.get("must_include", []),
                "must_not_include": case.get("must_not_include", []),
            }
            plans.append(plan)

        plan_path = self.output_dir / "cli_run_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)

        print(f"[PLAN] {len(plans)} CLI test plans → {plan_path}")
        return plans


def run_cli_cases(
    case_file: str | None = None,
    config_path: str | None = None,
    execute: bool = False,
) -> List[dict]:
    """Main entry point for CLI regression experiments.

    Args:
        case_file: Path to JSONL case file (defaults to examples/cli/cases.jsonl)
        config_path: Path to YAML config file
        execute: If True, run commands; if False, generate plan only
    """
    cfg = load_config(LAB_ROOT, Path(config_path) if config_path else None)
    cfg["output"]["dir"] = resolve_output_dir(cfg, LAB_ROOT)

    cf = case_file or str(LAB_ROOT / "examples" / "cli" / "cases.jsonl")
    cases = load_cases_list(cf)
    print(f"[INFO] Loaded {len(cases)} cases from {cf}")

    runner = CLIRunner(LAB_ROOT, cfg)

    if execute:
        return runner.run_all(cases)
    else:
        return runner.run_plan(cases)


def run_cli_cases_cli():
    """CLI entry point for CLI runner."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab CLI Case Runner")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Generate run plan (default if no --run)")
    parser.add_argument("--run", action="store_true", help="Execute CLI commands")
    parser.add_argument("--config", default=None, help="Config file path")
    args = parser.parse_args()

    run_cli_cases(
        case_file=args.case_file,
        config_path=args.config,
        execute=args.run,
    )


if __name__ == "__main__":
    run_cli_cases_cli()
