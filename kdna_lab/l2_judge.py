"""KDNA Lab — L2 LLM Judge.

Uses an LLM to score domain outputs against rubrics using semantic
evaluation, complementing L1's exact substring matching.

The judge is provider-agnostic — it uses the same multi-provider
infrastructure as the experiment runner.
"""

import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple


JUDGE_SYSTEM_PROMPT = """You are a KDNA Lab L2 judge. Your job is to score an AI output against a rubric.

Rules:
1. Score each rubric dimension from 0 to its max score (specified in the rubric).
2. For each dimension, provide a brief (1 sentence) reason for the score.
3. Be strict but fair. A max score requires near-perfect execution of that dimension.
4. Judge substance, not style. A fluent wrong answer is still wrong.
5. Output ONLY valid JSON. No markdown, no commentary.

Output format:
{
  "scores": {
    "<dimension>": {"score": <int>, "max": <int>, "reason": "<string>"}
  },
  "total": <int>,
  "max_total": <int>,
  "passed": <bool>,
  "summary": "<1-sentence overall assessment>"
}

Pass threshold: >= 60% of max_total is considered passing."""


def build_judge_prompt(case: Dict, output_body: str) -> str:
    """Build the L2 judge evaluation prompt."""
    rubric = case.get("rubric", {})
    rubric_lines = []
    for dim, max_score in rubric.items():
        rubric_lines.append(f"  {dim}: 0-{max_score} points")
    rubric_str = "\n".join(rubric_lines)

    max_total = sum(rubric.values()) if rubric else 10
    threshold = int(max_total * 0.6)

    return f"""Score this AI output against the rubric.

CASE INPUT:
{case.get('input', 'N/A')[:1500]}

EXPECTED BEHAVIOR:
{case.get('expected_behavior', 'comply')}

RUBRIC (max scores):
{rubric_str}

PASS THRESHOLD: >= {threshold}/{max_total}

OUTPUT TO SCORE:
---
{output_body[:3000]}
---

Score each rubric dimension. Output JSON only."""


def parse_judge_response(response: str) -> Dict[str, Any]:
    """Parse the LLM's JSON response, handling markdown wrapping."""
    # Try direct JSON first
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try extracting any JSON object
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {"error": "Failed to parse judge response", "raw": response[:500]}


def score_case_with_l2(
    case: Dict,
    output_body: str,
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    model: str = "deepseek/deepseek-v4-pro",
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """Score a single case output using L2 LLM Judge.

    Args:
        case: The test case definition (with rubric field)
        output_body: The actual LLM output text to score
        api_key: API key for the judge model
        base_url: API base URL
        model: Model to use for judging
        temperature: Low temperature for consistent judging

    Returns:
        L2 score dict: {scores, total, max_total, passed, summary}
    """
    from kdna_lab.providers import call_provider

    prompt = build_judge_prompt(case, output_body)

    result = call_provider(
        provider_name="openai_compatible",
        prompt=prompt,
        model=model,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )

    if result is None:
        return {"error": "Judge API call failed", "scores": {}, "total": 0, "max_total": 0, "passed": False}

    return parse_judge_response(result)


def score_batch_with_l2(
    cases: List[Dict],
    outputs: List[Dict],
    config: Dict | None = None,
    sample_size: int = 0,
) -> List[Dict]:
    """Score a batch of case outputs with L2 LLM Judge.

    Args:
        cases: Case definitions (must have rubric field)
        outputs: Output dicts with case_id, condition, output_body
        config: API config dict (provider, model, api_key_env, base_url)
        sample_size: If > 0, randomly sample this many cases (for cost control)

    Returns:
        List of {case_id, condition, L1_pass, L2} results
    """
    import random

    if config is None:
        config = {
            "provider": "openai_compatible",
            "model": "deepseek/deepseek-v4-pro",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
        }

    api_key = os.environ.get(config.get("api_key_env", "OPENAI_API_KEY"), "")

    case_map = {c["id"]: c for c in cases}

    items = list(outputs)
    if sample_size > 0 and len(items) > sample_size:
        items = random.sample(items, sample_size)

    results = []
    for item in items:
        cid = item["case_id"]
        case = case_map.get(cid)
        if not case or not case.get("rubric"):
            results.append({"case_id": cid, "condition": item.get("condition", ""),
                          "L2": {"error": "No rubric in case definition", "passed": False}})
            continue

        output_body = item.get("output_body", item.get("output", ""))
        l2 = score_case_with_l2(case, output_body, api_key=api_key,
                                base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
                                model=config.get("model", "deepseek/deepseek-v4-pro"))

        results.append({
            "case_id": cid,
            "condition": item.get("condition", ""),
            "L1_pass": item.get("L1_pass"),
            "L2": l2,
        })

    return results


def generate_l2_report(l2_results: List[Dict], output_path: str) -> str:
    """Generate L2 scoring report."""
    lines = []
    lines.append("# L2 LLM Judge Report")
    lines.append("")
    lines.append(f"**Cases scored:** {len(l2_results)}")
    lines.append("")

    total_l2_pass = sum(1 for r in l2_results if r.get("L2", {}).get("passed"))
    avg_score = sum(
        r.get("L2", {}).get("total", 0) for r in l2_results
        if r.get("L2", {}).get("total") is not None
    )
    avg_max = sum(
        r.get("L2", {}).get("max_total", 10) for r in l2_results
        if r.get("L2", {}).get("max_total") is not None
    )

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| L2 Pass Rate | {total_l2_pass}/{len(l2_results)} ({round(total_l2_pass/len(l2_results)*100) if l2_results else 0}%) |")
    if l2_results:
        lines.append(f"| Avg Score | {avg_score:.1f}/{avg_max:.0f} ({round(avg_score/avg_max*100) if avg_max else 0}%) |")
    lines.append("")

    # Per-condition breakdown
    by_cond: Dict[str, Dict] = {}
    for r in l2_results:
        cond = r.get("condition", "unknown")
        by_cond.setdefault(cond, {"total": 0, "pass": 0, "scores": []})
        by_cond[cond]["total"] += 1
        l2 = r.get("L2", {})
        if l2.get("passed"):
            by_cond[cond]["pass"] += 1
        if l2.get("total") is not None:
            by_cond[cond]["scores"].append(l2["total"])

    lines.append("## By Condition")
    lines.append("")
    lines.append("| Condition | L2 Pass | Avg Score |")
    lines.append("|-----------|---------|-----------|")
    for cond, stats in by_cond.items():
        avg = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        lines.append(f"| {cond} | {stats['pass']}/{stats['total']} | {avg:.1f} |")
    lines.append("")

    lines.append("## Details")
    lines.append("")
    for r in l2_results:
        l2 = r.get("L2", {})
        status = "PASS" if l2.get("passed") else ("FAIL" if l2.get("scores") else "ERR")
        lines.append(f"### {r['case_id']} [{r.get('condition','?')}] — {status}")
        lines.append(f"L1: {'PASS' if r.get('L1_pass') else 'FAIL'}")
        if l2.get("total") is not None:
            lines.append(f"L2: {l2['total']}/{l2.get('max_total','?')}")
        if l2.get("summary"):
            lines.append(f"> {l2['summary']}")
        if l2.get("error"):
            lines.append(f"Error: {l2['error']}")
        lines.append("")

    lines.append("---")
    lines.append("*L2 Judge assesses semantic quality, not just exact phrase matching.*")

    from pathlib import Path
    Path(output_path).write_text("\n".join(lines))
    return output_path


def l2_judge_cli():
    """CLI entry point for L2 Judge."""
    import argparse, sys
    from kdna_lab.paths import LAB_ROOT
    from kdna_lab.cases import load_cases_list

    parser = argparse.ArgumentParser(description="KDNA Lab L2 LLM Judge")
    parser.add_argument("--case-file", default="examples/writing/cases.jsonl")
    parser.add_argument("--results-file", required=True, help="JSON results file from experiment")
    parser.add_argument("--sample", type=int, default=10, help="How many cases to score (0=all)")
    parser.add_argument("--model", default="deepseek/deepseek-v4-pro")
    parser.add_argument("--condition", default=None, help="Filter by condition (e.g. kdna_full)")
    args = parser.parse_args()

    cases = load_cases_list(args.case_file)

    with open(args.results_file) as f:
        data = json.load(f)
    outputs = data.get("results", data)

    if args.condition:
        outputs = [o for o in outputs if o.get("condition") == args.condition]

    print(f"Cases: {len(cases)}, Results: {len(outputs)}, Sample: {args.sample}")

    config = {
        "provider": "openai_compatible",
        "model": args.model,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    }

    results = score_batch_with_l2(cases, outputs, config, sample_size=args.sample)

    l2_path = str(LAB_ROOT / "reports" / "l2_judge_report.md")
    generate_l2_report(results, l2_path)
    print(f"Report: {l2_path}")

    l2_pass = sum(1 for r in results if r.get("L2", {}).get("passed"))
    print(f"L2 Pass: {l2_pass}/{len(results)} ({round(l2_pass/len(results)*100) if results else 0}%)")


if __name__ == "__main__":
    l2_judge_cli()
