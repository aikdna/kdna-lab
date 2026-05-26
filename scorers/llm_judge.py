#!/usr/bin/env python3
"""
KDNA Lab — L2 LLM Judge

Uses an LLM to score domain outputs against a rubric.
Produces structured scores with reasoning for each dimension.

Requires: openai package (pip install openai)
Config: configs/default.yaml → api section
"""

import json
import os
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent

JUDGE_SYSTEM_PROMPT = """You are a KDNA Lab L2 judge. Your job is to score an AI agent's output against a defined rubric.

Rules:
1. Score each rubric dimension from 0 to its max score.
2. For each dimension, provide a brief (1-sentence) reason for the score.
3. Be strict but fair. A score of max requires near-perfect execution.
4. Do NOT be lenient just because the output is fluent. Judge substance, not style.
5. Output ONLY valid JSON with the exact structure shown. No markdown, no commentary.

Output format:
{
  "scores": {
    "<dimension>": {"score": <int>, "max": <int>, "reason": "<string>"}
  },
  "total": <int>,
  "max_total": <int>,
  "passed": <true|false>,
  "summary": "<1-sentence overall assessment>"
}
"""

def load_config():
    config_path = LAB_ROOT / "configs" / "default.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}

def call_llm(system_prompt, user_prompt, config, temperature=0.2):
    api = config.get("api", {})
    provider = api.get("provider", "openai")
    model = api.get("model", "gpt-4o")
    api_key = os.environ.get(api.get("api_key_env", "OPENAI_API_KEY"), "")
    base_url = api.get("base_url")

    if not api_key:
        return None, "No API key configured."

    if provider == "openai" or base_url:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=2000
            )
            return response.choices[0].message.content, None
        except ImportError:
            return None, "openai package not installed. Run: pip install openai"
        except Exception as e:
            return None, str(e)

    return None, f"Unsupported provider: {provider}"

def build_judge_prompt(case, output_body):
    rubric = case.get("rubric", {})
    rubric_str = "\n".join([f"  - {k}: 0-{v} points" for k, v in rubric.items()])
    threshold = sum(rubric.values()) * 0.8 if rubric else 0

    return f"""Score this AI output against the rubric.

CASE INPUT:
{case.get('input', 'N/A')}

EXPECTED BEHAVIOR:
{case.get('expected_behavior', 'comply')}

RUBRIC (max scores):
{rubric_str}

PASS THRESHOLD: >= {threshold:.0f} / {sum(rubric.values())}

OUTPUT TO SCORE:
---
{output_body[:4000]}
---

Score each rubric dimension. Output JSON only."""

def score_case(case, output_body, config):
    prompt = build_judge_prompt(case, output_body)
    response, error = call_llm(JUDGE_SYSTEM_PROMPT, prompt, config)

    if error:
        return {"error": error, "scores": {}, "total": 0, "max_total": 0, "passed": False}

    # Parse JSON from response
    import re
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            return result
        except json.JSONDecodeError:
            pass

    return {"error": f"Failed to parse JSON from response", "raw_response": response[:500],
            "scores": {}, "total": 0, "max_total": 0, "passed": False}

def score_batch(cases_file, outputs_dir, config):
    """Score all cases that have output files."""
    cases = {}
    with open(cases_file) as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                cases[c["id"]] = c

    raw_dir = Path(outputs_dir) / "raw"
    if not raw_dir.exists():
        print(f"[ERROR] Output directory not found: {raw_dir}")
        return []

    results = []
    for txt_file in sorted(raw_dir.glob("*.txt")):
        # Parse case_id from filename
        case_id = None
        for cid in cases:
            if cid in txt_file.stem:
                case_id = cid
                break
        if case_id is None or case_id not in cases:
            continue

        content = txt_file.read_text()
        body = content
        for line in content.split("\n"):
            if line.strip() == "---":
                body = content.split("---", 1)[1].strip()
                break

        print(f"[JUDGE] {case_id} ... ", end="", flush=True)
        l2 = score_case(cases[case_id], body, config)
        status = "PASS" if l2.get("passed") else ("FAIL" if l2.get("scores") else "ERR")
        print(status)

        results.append({
            "case_id": case_id,
            "L2": l2
        })

    # Save results
    output_path = Path(outputs_dir) / "l2_scores.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[JUDGE] Results → {output_path}")

    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab L2 LLM Judge")
    parser.add_argument("case_file", nargs="?", help="JSONL case file")
    parser.add_argument("--output-dir", default=None, help="Directory with raw outputs")
    parser.add_argument("--case-id", help="Score a single case by ID")
    parser.add_argument("--input-text", help="Direct input text for single-case scoring")
    parser.add_argument("--rubric", help="Rubric JSON for single-case scoring")
    args = parser.parse_args()

    config = load_config()
    output_dir = args.output_dir or str(LAB_ROOT / "outputs")

    if args.case_id and args.input_text and args.rubric:
        case = {"id": args.case_id, "input": args.case_id, "expected_behavior": "comply", "rubric": json.loads(args.rubric)}
        result = score_case(case, args.input_text, config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    case_file = args.case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    results = score_batch(case_file, output_dir, config)

    if results:
        passed = sum(1 for r in results if r.get("L2", {}).get("passed", False))
        print(f"\nSummary: {passed}/{len(results)} passed L2 evaluation")

if __name__ == "__main__":
    main()
