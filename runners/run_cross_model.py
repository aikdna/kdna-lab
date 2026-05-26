#!/usr/bin/env python3
"""
KDNA Lab — Cross-Model Runner

Runs the same domain cases across multiple models and compares results.
Produces a cross-model consistency matrix.

Modes:
  --plan    Generate execution matrix
  --run     Execute across configured models
  --compare Compare existing outputs across models
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LAB_ROOT = Path(__file__).resolve().parent.parent

def load_config():
    config_path = LAB_ROOT / "configs" / "default.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"models": [{"id": "default", "provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}]}

def load_cases(case_file):
    cases = []
    with open(case_file) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases

def load_domain_prompt(domain_name):
    import subprocess
    result = subprocess.run(f"kdna load {domain_name} --as=prompt", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout

def call_model(prompt, model_config):
    provider = model_config.get("provider", "openai")
    model = model_config.get("model", "gpt-4o")
    api_key = os.environ.get(model_config.get("api_key_env", "OPENAI_API_KEY"), "")
    base_url = model_config.get("base_url")

    if not api_key:
        return None, f"No API key for {model_config['id']}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, str(e)

def check_l1_pass(output, must_include, must_not_include):
    missing = [m for m in must_include if m.lower() not in output.lower()]
    violations = [m for m in must_not_include if m.lower() in output.lower()]
    return len(missing) == 0 and len(violations) == 0, missing, violations

def run_matrix(cases, domain, models, output_dir):
    domain_prompt = load_domain_prompt(domain)
    if domain_prompt is None:
        print(f"[ERROR] Failed to load domain: {domain}")
        return

    run_id = datetime.now().strftime("cross_%Y%m%d_%H%M%S")
    raw_dir = Path(output_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = []

    total = len(cases) * len(models)
    n = 0

    for case in cases:
        for model_config in models:
            n += 1
            model_id = model_config["id"]
            prompt = f"{domain_prompt}\n\nApply silently.\n\n[INPUT]\n{case['input']}"

            print(f"[RUN] ({n}/{total}) {case['id']} @ {model_id} ... ", end="", flush=True)
            output, error = call_model(prompt, model_config)

            if error:
                print(f"ERR: {error}")
                continue

            # Save raw output
            outpath = raw_dir / f"{run_id}_{case['id']}_{model_id}.txt"
            with open(outpath, "w") as f:
                f.write(f"# Run: {run_id}\n# Case: {case['id']}\n# Model: {model_id}\n---\n{output}")

            # Quick L1 check
            l1_pass, missing, violations = check_l1_pass(
                output,
                case.get("must_include", []),
                case.get("must_not_include", [])
            )

            results.append({
                "run_id": run_id,
                "case_id": case["id"],
                "model": model_id,
                "L1_pass": l1_pass,
                "missing": missing,
                "violations": violations,
                "output_path": str(outpath),
                "char_count": len(output)
            })

            status = "OK" if l1_pass else f"FAIL(missing={len(missing)},violations={len(violations)})"
            print(status)

            time.sleep(0.5)

    # Save results index
    index_path = Path(output_dir) / f"{run_id}_cross_model_index.json"
    with open(index_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate matrix
    matrix = generate_matrix(results, cases, models)
    matrix_path = Path(output_dir) / f"{run_id}_matrix.md"
    with open(matrix_path, "w") as f:
        f.write(matrix)

    # Summary
    passed = sum(1 for r in results if r["L1_pass"])
    print(f"\n[EXEC] {passed}/{len(results)} passed L1")
    print(f"[EXEC] Matrix → {matrix_path}")
    print(f"[EXEC] Index → {index_path}")

    return results

def generate_matrix(results, cases, models):
    lines = []
    lines.append("# Cross-Model L1 Matrix")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Header
    model_ids = [m["id"] for m in models]
    header = "| Case | " + " | ".join(model_ids) + " |"
    lines.append(header)
    lines.append("|------" + "|------" * len(model_ids) + "|")

    # Rows
    for case in cases:
        row = f"| {case['id']} |"
        for model_id in model_ids:
            matches = [r for r in results if r["case_id"] == case["id"] and r["model"] == model_id]
            if matches:
                r = matches[0]
                if r["L1_pass"]:
                    row += " ✅ |"
                else:
                    details = []
                    if r["missing"]:
                        details.append(f"miss:{len(r['missing'])}")
                    if r["violations"]:
                        details.append(f"viol:{len(r['violations'])}")
                    row += f" ❌ ({','.join(details)}) |"
            else:
                row += " - |"
        lines.append(row)

    lines.append("")
    lines.append("## Failed Details")
    lines.append("")

    for r in results:
        if not r["L1_pass"]:
            lines.append(f"### {r['case_id']} @ {r['model']}")
            if r["missing"]:
                lines.append(f"- Missing: {r['missing']}")
            if r["violations"]:
                lines.append(f"- Violations: {r['violations']}")
            lines.append("")

    # Consistency analysis
    lines.append("## Consistency Analysis")
    lines.append("")
    case_consistency = defaultdict(lambda: {"pass": 0, "fail": 0, "models": []})
    for r in results:
        key = r["case_id"]
        if r["L1_pass"]:
            case_consistency[key]["pass"] += 1
        else:
            case_consistency[key]["fail"] += 1
            case_consistency[key]["models"].append(r["model"])

    for case_id, stats in case_consistency.items():
        total_models = stats["pass"] + stats["fail"]
        if total_models == len(models) and stats["pass"] == len(models):
            lines.append(f"- **{case_id}**: Consistent PASS across all {len(models)} models ✅")
        elif stats["fail"] > 0 and stats["pass"] > 0:
            lines.append(f"- **{case_id}**: Inconsistent — failed on {stats['models']}")
        elif stats["fail"] == len(models):
            lines.append(f"- **{case_id}**: Consistent FAIL across all models ❌")

    return "\n".join(lines)

def compare_mode(results_dir, output_dir):
    """Compare existing runs across models from stored results."""
    index_files = list(Path(results_dir).glob("*_cross_model_index.json"))
    if not index_files:
        print("[ERROR] No cross-model index files found.")
        return

    print(f"[INFO] Found {len(index_files)} cross-model run(s)")
    for idx_file in index_files:
        with open(idx_file) as f:
            results = json.load(f)
        print(f"\n  {idx_file.name}: {len(results)} results")

        passed = sum(1 for r in results if r.get("L1_pass"))
        print(f"  Passed: {passed}/{len(results)}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Cross-Model Runner")
    parser.add_argument("case_file", nargs="?", help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Show execution plan")
    parser.add_argument("--run", action="store_true", help="Execute across models")
    parser.add_argument("--compare", action="store_true", help="Compare existing results")
    parser.add_argument("--domain", default=None, help="Domain name override")
    parser.add_argument("--models", default=None, help="Comma-separated model IDs to use")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    config = load_config()
    domain = args.domain or config.get("domain", {}).get("name", "@aikdna/kdna_propagation")
    output_dir = args.output_dir or config.get("output", {}).get("dir") or str(LAB_ROOT / "outputs")
    if not os.path.isabs(output_dir):
        output_dir = str(LAB_ROOT / output_dir)

    if args.compare:
        compare_mode(output_dir, output_dir)
        return

    case_file = args.case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    cases = load_cases(case_file)
    models = config.get("models", [{"id": "default", "provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}])

    if args.models:
        selected = args.models.split(",")
        models = [m for m in models if m["id"] in selected]

    if args.plan:
        print(f"[PLAN] Domain: {domain}")
        print(f"[PLAN] Cases: {len(cases)}")
        print(f"[PLAN] Models: {[m['id'] for m in models]}")
        print(f"[PLAN] Total runs: {len(cases) * len(models)}")
        return

    if args.run:
        results = run_matrix(cases, domain, models, output_dir)
    else:
        print(f"Use --plan to preview, --run to execute, --compare to analyze existing results.")

if __name__ == "__main__":
    main()
