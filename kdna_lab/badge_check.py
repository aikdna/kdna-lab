"""KDNA Lab — Quality Badge Evidence Gate.

Automates the quality badge computation defined in:
  specs/quality-badge-evidence-gate.md

Badge levels:
  draft    — basic structure: has required files, passes schema validation
  tested   — draft + L1 tests pass above threshold + has eval cases
  trusted  — tested + L2 + cross-model consistency + human review

This module checks which badge level a domain qualifies for
based on evidence from the lab's checkers and scoring pipeline.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from kdna_lab.paths import LAB_ROOT
from kdna_lab.schema_check import resolve_schema_dir, validate_domain_directory


BADGE_LEVELS = ["draft", "tested", "trusted"]
BADGE_DESCRIPTIONS = {
    "draft": "Basic structure: has required files, passes schema validation.",
    "tested": "Draft + L1 tests pass ≥80% + has eval cases defined.",
    "trusted": "Tested + L2 judge pass ≥70% + cross-model consistency + human review.",
}


class BadgeChecker:
    """Compute quality badge level for a KDNA domain based on evidence."""

    def __init__(self, lab_root: Path | None = None):
        self.lab_root = lab_root or LAB_ROOT
        self.schemas_dir = resolve_schema_dir()
        self.store_dir = self.lab_root / "evidence"

    def check(self, domain_name: str, domain_path: Path | None = None,
              l1_pass_rate: Optional[float] = None,
              l2_pass_rate: Optional[float] = None,
              has_eval_cases: bool = False,
              cross_model_consistent: Optional[bool] = None,
              human_reviewed: bool = False,
              ) -> Dict[str, Any]:
        """Run full badge computation.

        Args:
            domain_name: Domain name (e.g. @aikdna/writing)
            domain_path: Path to domain source or installed directory
            l1_pass_rate: L1 pass rate percentage (from scoring pipeline)
            l2_pass_rate: L2 pass rate percentage
            has_eval_cases: Whether eval cases are defined
            cross_model_consistent: Whether cross-model tests pass
            human_reviewed: Whether L3 human review has been done
        """
        checks = {}
        qualified_level = None

        # ---- draft checks ----
        schema_valid = False
        schema_errors: List[str] = []

        if domain_path:
            results = validate_domain_directory(Path(domain_path), self.schemas_dir)
            schema_valid = all(r["valid"] for r in results)
            schema_errors = [
                e for r in results for f in r.get("files", [])
                for e in f.get("errors", [])
            ]
        else:
            schema_errors.append("Domain path not provided; schema check skipped.")

        checks["draft"] = {
            "schema_valid": schema_valid,
            "schema_errors": schema_errors,
            "passed": schema_valid,
        }

        if checks["draft"]["passed"]:
            qualified_level = "draft"

            # ---- tested checks ----
            l1_ok = (l1_pass_rate or 0) >= 80
            checks["tested"] = {
                "l1_pass_rate": l1_pass_rate,
                "l1_threshold_met": l1_ok,
                "has_eval_cases": has_eval_cases,
                "passed": l1_ok and has_eval_cases,
            }

            if checks["tested"]["passed"]:
                qualified_level = "tested"

                # ---- trusted checks ----
                l2_ok = (l2_pass_rate or 0) >= 70
                checks["trusted"] = {
                    "l2_pass_rate": l2_pass_rate,
                    "l2_threshold_met": l2_ok,
                    "cross_model_consistent": cross_model_consistent,
                    "human_reviewed": human_reviewed,
                    "passed": l2_ok and cross_model_consistent and human_reviewed,
                }

                if checks["trusted"]["passed"]:
                    qualified_level = "trusted"

        return {
            "domain": domain_name,
            "qualified_level": qualified_level,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }


def generate_badge_report(result: Dict, output_path: str) -> str:
    """Generate a human-readable badge evidence report."""
    lines = []
    lines.append(f"# Quality Badge Report: {result['domain']}")
    lines.append("")
    lines.append(f"**Qualified Level:** `{result['qualified_level']}`")
    lines.append(f"**Date:** {result['timestamp'][:19]}")
    lines.append("")

    for level in BADGE_LEVELS:
        check = result["checks"].get(level)
        if check is None:
            continue

        status = "PASS" if check["passed"] else ("NOT MET" if result["qualified_level"] is None else "SKIPPED")
        lines.append(f"## {level.title()} — {status}")
        lines.append(f"*{BADGE_DESCRIPTIONS[level]}*")
        lines.append("")

        if level == "draft":
            lines.append(f"- Schema valid: {check['schema_valid']}")
            if check.get("schema_errors"):
                for e in check["schema_errors"][:5]:
                    lines.append(f"  - {e}")
        elif level == "tested":
            lines.append(f"- L1 pass rate: {check.get('l1_pass_rate', 'N/A')}% (need ≥80%)")
            lines.append(f"- Has eval cases: {check.get('has_eval_cases', False)}")
        elif level == "trusted":
            lines.append(f"- L2 pass rate: {check.get('l2_pass_rate', 'N/A')}% (need ≥70%)")
            lines.append(f"- Cross-model consistent: {check.get('cross_model_consistent', 'N/A')}")
            lines.append(f"- Human reviewed: {check.get('human_reviewed', False)}")
        lines.append("")

    lines.append("## Requirements Summary")
    lines.append("")
    lines.append("| Level | Requirement | Status |")
    lines.append("|-------|------------|--------|")
    for level in BADGE_LEVELS:
        badge_level = BADGE_LEVELS.index(level)
        qualified_level_idx = BADGE_LEVELS.index(result["qualified_level"]) if result["qualified_level"] else -1
        if badge_level <= qualified_level_idx:
            lines.append(f"| `{level}` | All checks passed | ✅ |")
        elif badge_level == qualified_level_idx + 1 and result["checks"].get(level):
            lines.append(f"| `{level}` | Next target | 🔲 |")
        else:
            lines.append(f"| `{level}` | Not yet applicable | — |")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by KDNA Lab Badge Evidence Gate.*")

    Path(output_path).write_text("\n".join(lines))
    return output_path


def badge_cli():
    """CLI entry point for quality badge checking."""
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Quality Badge Evidence Gate")
    parser.add_argument("domain", help="Domain name or path")
    parser.add_argument("--domain-path", default=None, help="Path to domain source directory")
    parser.add_argument("--l1-rate", type=float, default=None, help="L1 pass rate (%)")
    parser.add_argument("--l2-rate", type=float, default=None, help="L2 pass rate (%)")
    parser.add_argument("--eval-cases", action="store_true", help="Has eval cases")
    parser.add_argument("--cross-model", action="store_true", help="Cross-model consistent")
    parser.add_argument("--human-reviewed", action="store_true", help="Human review completed")
    parser.add_argument("--output", default=None, help="Output report path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    checker = BadgeChecker()
    result = checker.check(
        domain_name=args.domain,
        domain_path=Path(args.domain_path) if args.domain_path else None,
        l1_pass_rate=args.l1_rate,
        l2_pass_rate=args.l2_rate,
        has_eval_cases=args.eval_cases,
        cross_model_consistent=args.cross_model,
        human_reviewed=args.human_reviewed,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        out_path = args.output or str(LAB_ROOT / "reports" / f"badge_{args.domain.replace('@','').replace('/','_')}.md")
        path = generate_badge_report(result, out_path)
        print(f"\nDomain: {result['domain']}")
        print(f"Qualified badge: {result['qualified_level']}")
        print(f"Report: {path}")


if __name__ == "__main__":
    badge_cli()
