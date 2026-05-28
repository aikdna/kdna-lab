"""KDNA Lab — Cross-Agent Portability Tester.

Tests whether the same KDNA domain produces consistent judgment behavior
across different AI agent environments (Claude Code, OpenCode, Cursor, etc.).

Key research question:
  "KDNA judgment assets are portable across agents, but require load profiles
   and required-output blocks for stability."
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from kdna_lab.cases import load_cases_list
from kdna_lab.checks import check_must_include, check_must_not_include
from kdna_lab.config import load_config, resolve_output_dir
from kdna_lab.paths import LAB_ROOT
from kdna_lab.runner import ExperimentRunner
from kdna_lab.evidence_store import EvidenceStore


# ---- Agent Profiles ----

# Each profile represents a real AI agent environment.
# The system_prompt mimics what that agent adds before user input.
# The instruction_style affects how requests are phrased.

AGENT_PROFILES = {
    "claude_code": {
        "id": "claude_code",
        "name": "Claude Code",
        "description": "Anthropic's coding agent via Claude Code CLI",
        "system_prompt": (
            "You are Claude Code, Anthropic's official CLI agent for software engineering. "
            "You have access to Bash, file editing, and search tools. "
            "Follow instructions precisely. Be thorough. Favor correctness over brevity."
        ),
        "instruction_style": "verbose",
        "default_model": "claude-sonnet-4-20250514",
        "provider": "anthropic",
    },
    "opencode": {
        "id": "opencode",
        "name": "OpenCode",
        "description": "Open-source CLI agent with extensive skill system",
        "system_prompt": (
            "You are opencode, an interactive CLI tool for software engineering. "
            "You have access to bash, file read/write/edit, glob, grep, and specialized skills. "
            "Be concise. Use tools efficiently. Follow existing code conventions."
        ),
        "instruction_style": "concise",
        "default_model": "gpt-4o",
        "provider": "openai",
    },
    "chatgpt": {
        "id": "chatgpt",
        "name": "ChatGPT",
        "description": "General-purpose conversational AI assistant",
        "system_prompt": (
            "You are ChatGPT, a helpful AI assistant. "
            "You provide clear, accurate, and safe responses. "
            "When in doubt, ask clarifying questions rather than making assumptions."
        ),
        "instruction_style": "verbose",
        "default_model": "gpt-4o",
        "provider": "openai",
    },
    "raw_model": {
        "id": "raw_model",
        "name": "Raw Model (No Agent)",
        "description": "Direct model call with minimal system prompt — baseline",
        "system_prompt": "You are a helpful AI assistant.",
        "instruction_style": "concise",
        "default_model": "gpt-4o",
        "provider": "openai",
    },
    "kdna_agent": {
        "id": "kdna_agent",
        "name": "KDNA-Native Agent",
        "description": "Hypothetical agent with built-in KDNA support",
        "system_prompt": (
            "You are a KDNA-native AI agent. You have built-in support for "
            "loading KDNA domains, tracing judgment paths, and producing "
            "structured judgment reports with trace artifacts."
        ),
        "instruction_style": "verbose",
        "default_model": "gpt-4o",
        "provider": "openai",
    },
}


class PortabilityRunner(ExperimentRunner):
    """Run cross-agent portability tests."""

    def __init__(self, lab_root: Path, config: Dict[str, Any], agents: List[str] | None = None):
        super().__init__(lab_root, config)
        agent_ids = agents or list(AGENT_PROFILES.keys())
        self.agent_profiles = {aid: AGENT_PROFILES[aid] for aid in agent_ids if aid in AGENT_PROFILES}

    def _build_prompt(self, domain_prompt: str, agent_profile: Dict, case: dict) -> str:
        """Build a prompt for a specific agent profile."""
        parts = [agent_profile["system_prompt"]]
        parts.append("")
        parts.append("--- IMPORTANT INSTRUCTIONS ---")
        parts.append(domain_prompt)
        parts.append("--- END INSTRUCTIONS ---")
        parts.append("")
        parts.append(f"Task: {case['input']}")
        parts.append("")
        if agent_profile.get("instruction_style") == "concise":
            parts.append("Be concise. Output only what is requested.")
        return "\n".join(parts)

    def run_all(
        self,
        cases: List[dict],
        domain: str | None = None,
        rate_limit: float = 0.5,
    ) -> List[dict]:
        """Run all cases across all agent profiles."""
        domain_name = domain or self.config.get("domain", {}).get("name", "@aikdna/kdna_propagation")
        domain_prompt = self.load_domain_prompt(domain_name)
        if domain_prompt is None:
            raise RuntimeError(f"Failed to load domain: {domain_name}")

        results = []
        total = len(cases) * len(self.agent_profiles)
        n = 0

        for case in cases:
            for agent_id, agent_profile in self.agent_profiles.items():
                n += 1
                prompt = self._build_prompt(domain_prompt, agent_profile, case)
                model = agent_profile.get("default_model", "gpt-4o")

                print(f"  [{n}/{total}] {case['id']} @ {agent_id} ... ", end="", flush=True)
                output = self.call_api(prompt)

                if output is None:
                    print("FAILED")
                    results.append({
                        "case_id": case["id"],
                        "agent": agent_id,
                        "agent_name": agent_profile["name"],
                        "model": model,
                        "L1_pass": False,
                        "error": "API call failed",
                        "missing": case.get("must_include", []),
                        "violations": [],
                    })
                    continue

                mi_pass, mi_results = check_must_include(output, case.get("must_include", []))
                mni_pass, mni_violations = check_must_not_include(
                    output, case.get("must_not_include", [])
                )
                l1_pass = mi_pass and mni_pass
                missing = [r["item"] for r in mi_results if not r["found"]] if not mi_pass else []

                outpath = self.save_output(
                    f"{case['id']}_{agent_id}",
                    output,
                    _ext="txt",
                    Run=self.run_id,
                    Case=case["id"],
                    Agent=agent_id,
                    Model=model,
                )

                results.append({
                    "run_id": self.run_id,
                    "case_id": case["id"],
                    "agent": agent_id,
                    "agent_name": agent_profile["name"],
                    "model": model,
                    "L1_pass": l1_pass,
                    "missing": missing,
                    "violations": mni_violations,
                    "output_path": outpath,
                    "char_count": len(output),
                })

                status = "OK" if l1_pass else f"FAIL(m={len(missing)},v={len(mni_violations)})"
                print(status)
                time.sleep(rate_limit)

        self.save_index(results)
        return results

    def run_plan(self, cases: List[dict], domain: str | None = None) -> List[dict]:
        """Generate cross-agent execution plan without API calls."""
        domain_name = domain or self.config.get("domain", {}).get("name", "@aikdna/kdna_propagation")
        domain_prompt = self.load_domain_prompt(domain_name)
        if domain_prompt is None:
            raise RuntimeError(f"Failed to load domain: {domain_name}")

        plans = []
        for case in cases:
            for agent_id, agent_profile in self.agent_profiles.items():
                plans.append({
                    "run_id": self.run_id,
                    "case_id": case["id"],
                    "agent": agent_id,
                    "agent_name": agent_profile["name"],
                    "prompt": self._build_prompt(domain_prompt, agent_profile, case),
                    "must_include": case.get("must_include", []),
                    "must_not_include": case.get("must_not_include", []),
                })

        plan_path = self.output_dir / f"{self.run_id}_portability_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)

        print(f"[PLAN] {len(plans)} test plans → {plan_path}")
        print(f"[PLAN] Cases: {len(cases)}, Agents: {list(self.agent_profiles.keys())}")
        return plans


# ---- Portability Analysis ----

def analyze_portability(results: List[Dict]) -> Dict[str, Any]:
    """Analyze cross-agent portability from scored results.

    Returns:
        per_case: consistency metrics per test case
        per_agent: performance metrics per agent
        overall: aggregate consistency score
    """
    cases: Dict[str, List[Dict]] = defaultdict(list)
    agents: Dict[str, List[Dict]] = defaultdict(list)

    for r in results:
        cases[r["case_id"]].append(r)
        agents[r["agent"]].append(r)

    # Per-agent stats
    per_agent = {}
    for agent_id, agent_results in agents.items():
        passed = sum(1 for r in agent_results if r.get("L1_pass"))
        total_missing = sum(len(r.get("missing", [])) for r in agent_results)
        total_violations = sum(len(r.get("violations", [])) for r in agent_results)
        per_agent[agent_id] = {
            "agent_name": agent_results[0].get("agent_name", agent_id),
            "total": len(agent_results),
            "passed": passed,
            "pass_rate": round(passed / len(agent_results) * 100),
            "total_missing": total_missing,
            "total_violations": total_violations,
        }

    # Per-case consistency
    per_case = {}
    for case_id, case_results in cases.items():
        agents_pass = {r["agent"]: r.get("L1_pass") for r in case_results}
        all_pass = all(agents_pass.values())
        all_fail = all(not p for p in agents_pass.values())
        inconsistent = not all_pass and not all_fail

        per_case[case_id] = {
            "agent_results": agents_pass,
            "all_pass": all_pass,
            "all_fail": all_fail,
            "inconsistent": inconsistent,
            "passing_agents": [a for a, p in agents_pass.items() if p],
            "failing_agents": [a for a, p in agents_pass.items() if not p],
        }

    # Overall
    total = len(results)
    overall_pass = sum(1 for r in results if r.get("L1_pass"))
    inconsistent_count = sum(1 for c in per_case.values() if c["inconsistent"])
    all_pass_count = sum(1 for c in per_case.values() if c["all_pass"])

    return {
        "total_runs": total,
        "overall_pass": overall_pass,
        "overall_pass_rate": round(overall_pass / total * 100) if total else 0,
        "cases_tested": len(cases),
        "agents_tested": len(agents),
        "consistent_pass": all_pass_count,
        "consistent_fail": sum(1 for c in per_case.values() if c["all_fail"]),
        "inconsistent_cases": inconsistent_count,
        "portability_score": round(all_pass_count / len(cases) * 100) if cases else 0,
        "per_agent": per_agent,
        "per_case": per_case,
    }


def generate_portability_report(analysis: Dict, output_path: str) -> str:
    """Generate cross-agent portability report."""
    lines = []
    lines.append("# Cross-Agent Portability Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"**Portability Score:** {analysis['portability_score']}%")
    lines.append(f"  ({analysis['consistent_pass']}/{analysis['cases_tested']} cases passed on all agents)")
    lines.append("")

    # Overall
    lines.append("## Overall")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total runs | {analysis['total_runs']} |")
    lines.append(f"| Overall pass | {analysis['overall_pass']} ({analysis['overall_pass_rate']}%) |")
    lines.append(f"| Agents tested | {analysis['agents_tested']} |")
    lines.append(f"| Consistent pass | {analysis['consistent_pass']} |")
    lines.append(f"| Inconsistent | {analysis['inconsistent_cases']} |")
    lines.append("")

    # Per-agent
    lines.append("## Per-Agent Performance")
    lines.append("")
    lines.append("| Agent | Passed | Rate | Missing | Violations |")
    lines.append("|-------|--------|------|---------|------------|")
    for agent_id, stats in analysis["per_agent"].items():
        lines.append(
            f"| {stats['agent_name']} | {stats['passed']}/{stats['total']} "
            f"| {stats['pass_rate']}% | {stats['total_missing']} | {stats['total_violations']} |"
        )
    lines.append("")

    # Per-case consistency
    lines.append("## Case-by-Case Consistency")
    lines.append("")
    agent_ids = sorted(analysis.get("agents_tested", []) or 
                       list(next(iter(analysis["per_case"].values()), {}).get("agent_results", {}).keys()))
    if not agent_ids:
        agent_ids = sorted(set(
            a for c in analysis["per_case"].values()
            for a in c.get("agent_results", {}).keys()
        ))

    header = "| Case | " + " | ".join(f"{aid[:6]}" for aid in agent_ids) + " | Consistent |"
    lines.append(header)
    lines.append("|------" + "|------" * (len(agent_ids) + 1) + "|")

    for case_id, stats in sorted(analysis["per_case"].items()):
        row = f"| {case_id} |"
        for aid in agent_ids:
            passed = stats.get("agent_results", {}).get(aid)
            if passed is True:
                row += " ✅ |"
            elif passed is False:
                row += " ❌ |"
            else:
                row += " — |"
        consistency = "✅ All" if stats["all_pass"] else ("❌ All" if stats["all_fail"] else "⚠ Mixed")
        row += f" {consistency} |"
        lines.append(row)
    lines.append("")

    # Inconsistent cases detail
    inconsistent = [(cid, s) for cid, s in analysis["per_case"].items() if s["inconsistent"]]
    if inconsistent:
        lines.append("## Inconsistent Cases (Portability Issues)")
        lines.append("")
        for cid, stats in inconsistent:
            lines.append(f"### {cid}")
            lines.append(f"- Passing: {', '.join(stats['passing_agents'])}")
            lines.append(f"- Failing: {', '.join(stats['failing_agents'])}")
            lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    if analysis["portability_score"] >= 80:
        lines.append("- **Good portability**: most cases pass consistently across agents")
    elif analysis["portability_score"] >= 50:
        lines.append("- **Moderate portability**: some cases are agent-dependent")
    else:
        lines.append("- **Low portability**: significant agent-specific behavior differences")

    lines.append(f"- {analysis['inconsistent_cases']} case(s) show agent-dependent behavior")
    lines.append(f"- {analysis['consistent_pass']} case(s) pass on all agents")

    worst_agent = min(analysis["per_agent"].items(), key=lambda x: x[1]["pass_rate"])
    best_agent = max(analysis["per_agent"].items(), key=lambda x: x[1]["pass_rate"])
    lines.append(f"- Best agent: {best_agent[1]['agent_name']} ({best_agent[1]['pass_rate']}%)")
    lines.append(f"- Worst agent: {worst_agent[1]['agent_name']} ({worst_agent[1]['pass_rate']}%)")
    lines.append("")

    lines.append("---")
    lines.append("*This report proves or disproves the claim that KDNA judgment assets are portable across agents.*")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def run_portability_test(
    case_file: str | None = None,
    domain: str | None = None,
    agents: List[str] | None = None,
    execute: bool = False,
    config_path: str | None = None,
) -> List[dict]:
    """Main entry point for cross-agent portability testing."""
    cfg = load_config(LAB_ROOT, Path(config_path) if config_path else None)
    cfg["output"]["dir"] = resolve_output_dir(cfg, LAB_ROOT)

    if domain:
        cfg.setdefault("domain", {})["name"] = domain

    cf = case_file or str(LAB_ROOT / "examples" / "kdna_propagation" / "cases.jsonl")
    cases = load_cases_list(cf)
    print(f"[INFO] Loaded {len(cases)} cases from {cf}")

    selected = agents or list(AGENT_PROFILES.keys())
    runner = PortabilityRunner(LAB_ROOT, cfg, agents=selected)
    print(f"[INFO] Agents: {[AGENT_PROFILES[a]['name'] for a in selected]}")

    if execute:
        results = runner.run_all(cases, domain=domain)
        analysis = analyze_portability(results)

        report_path = str(LAB_ROOT / "reports" / f"portability_{runner.run_id}.md")
        generate_portability_report(analysis, report_path)

        # Archive to Evidence Store
        try:
            store = EvidenceStore(LAB_ROOT / "evidence")
            store.ingest_run(
                run_id=runner.run_id,
                run_type="portability",
                target=domain or cfg.get("domain", {}).get("name", "unknown"),
                results=results,
                conditions=["cross_agent"],
                models=[p.get("default_model", "") for p in AGENT_PROFILES.values()
                        if p["id"] in (agents or AGENT_PROFILES.keys())],
                extra_meta={
                    "agents_tested": list(agent_profiles.keys()) if (agent_profiles := runner.agent_profiles) else [],
                    "portability_score": analysis["portability_score"],
                },
            )
        except Exception:
            pass

        passed = analysis["overall_pass"]
        total = analysis["total_runs"]
        print(f"\n[EXEC] {passed}/{total} passed L1 checks")
        print(f"[EXEC] Portability score: {analysis['portability_score']}%")
        print(f"[EXEC] Report → {report_path}")

        return results
    else:
        runner.run_plan(cases, domain=domain)
        return []


def portability_cli():
    """CLI entry point for portability testing."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Cross-Agent Portability Tester")
    parser.add_argument("case_file", nargs="?", default=None, help="JSONL case file")
    parser.add_argument("--plan", action="store_true", help="Generate test plan")
    parser.add_argument("--execute", action="store_true", help="Execute tests via API")
    parser.add_argument("--domain", default=None, help="Domain name override")
    parser.add_argument("--agents", default=None, help="Comma-separated agent IDs")
    parser.add_argument("--config", default=None, help="Config file path")
    parser.add_argument("--list-agents", action="store_true", help="List available agent profiles")
    args = parser.parse_args()

    if args.list_agents:
        print("\nAvailable Agent Profiles:")
        for aid, profile in AGENT_PROFILES.items():
            print(f"  {aid:20s} {profile['name']:30s} ({profile['provider']})")
            print(f"                     {profile['description']}")
        return

    agents = args.agents.split(",") if args.agents else None

    if args.execute:
        run_portability_test(
            case_file=args.case_file,
            domain=args.domain,
            agents=agents,
            execute=True,
            config_path=args.config,
        )
    else:
        run_portability_test(
            case_file=args.case_file,
            domain=args.domain,
            agents=agents,
            execute=False,
            config_path=args.config,
        )


if __name__ == "__main__":
    portability_cli()
