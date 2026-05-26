#!/usr/bin/env python3
"""
KDNA Lab — Patch Proposer

Reads failure analysis output and generates structured fix proposals
for SPEC, CLI, domain, schema, or test artifacts.

Proposals include:
- What to change (file, field, location)
- Why (evidence from failure analysis)
- Suggested new value or structure
- Regression tests to add
"""

import json
from pathlib import Path
from datetime import datetime

LAB_ROOT = Path(__file__).resolve().parent.parent

PATCH_TEMPLATES = {
    "canonical_phrase_missing": {
        "target_file": "KDNA_Patterns.json",
        "action": "add_field",
        "description": "Add `must_include` array to enforce required output phrases.",
        "example_change": {
            "KDNA_Patterns.json": {
                "must_include": [
                    "Trace 证明可检查性，不证明绝对正确。"
                ]
            }
        },
        "regression_tests": [
            "Add case checking that canonical phrase appears in all output types"
        ]
    },
    "banned_claim_leak": {
        "target_file": "KDNA_Patterns.json",
        "action": "add_banned_term",
        "description": "Add leaked term to banned_terms list with why and replace_with.",
        "example_change": {
            "KDNA_Patterns.json": {
                "terminology.banned_terms": [
                    {"term": "LEAKED_TERM", "why": "Overclaim risk.", "replace_with": "SAFE_TERM"}
                ]
            }
        },
        "regression_tests": [
            "Add overclaim_resistance case targeting the leaked term"
        ]
    },
    "schema_doc_mismatch": {
        "target_file": "SPEC.md or schema/*.schema.json",
        "action": "align_docs",
        "description": "Align SPEC documentation with JSON Schema requirements for the mismatched field.",
        "example_change": {
            "SPEC.md": "Document the field type, required sub-fields, and provide a valid example."
        },
        "regression_tests": [
            "Add schema validation case for each field type variant"
        ]
    },
    "cli_error_unclear": {
        "target_file": "CLI source (src/validate.js or similar)",
        "action": "improve_error_message",
        "description": "Include expected type, actual value, and fix example in error message.",
        "example_change": {
            "error_format": "{field}: expected {expected_type}, got {actual_type}. Example: {example}"
        },
        "regression_tests": [
            "Add CLI case checking error message contains type, example, fix guidance"
        ]
    },
    "fact_fabrication": {
        "target_file": "KDNA_Patterns.json or output schema",
        "action": "add_required_source_materials",
        "description": "Add mechanism for declaring data dependencies before writing.",
        "example_change": {
            "output_constraints": {
                "required_source_materials": ["field description when unknown"]
            }
        },
        "regression_tests": [
            "Add fact_discipline case with missing data"
        ]
    },
    "cross_model_inconsistency": {
        "target_file": "Loader (kdna load output format)",
        "action": "add_REQUIRED_OUTPUT_block",
        "description": "Add explicit REQUIRED_OUTPUT section to load output, separate from judgment guidance.",
        "example_change": {
            "kdna_load_output": "Split into REQUIRED_OUTPUT and JUDGMENT_GUIDANCE sections"
        },
        "regression_tests": [
            "Add cross-model case verifying canonical phrase appears in all models"
        ]
    },
    "figure_not_argumentative": {
        "target_file": "KDNA_Scenarios.json or output schema",
        "action": "strengthen_figure_schema",
        "description": "Require argument_role, visual_structure, and avoid_visuals fields in figure_plan.",
        "example_change": {
            "figure_plan": {
                "required_fields": ["argument_role", "visual_structure", "image_prompt_for_chatgpt"],
                "avoid_visuals_defaults": ["decorative sci-fi", "glowing circuits", "generic AI brain"]
            }
        },
        "regression_tests": [
            "Add figure_plan case checking argument_role is non-decorative"
        ]
    },
    "self_check_misleading": {
        "target_file": "KDNA_Patterns.json or schema",
        "action": "support_partial_status",
        "description": "Allow self_check items to have true/false/partial/n/a status with notes.",
        "example_change": {
            "self_check": [
                {"question": "...", "status": "true", "note": "explanation"}
            ]
        },
        "regression_tests": [
            "Add self_check case verifying partial/n/a status is accepted"
        ]
    }
}

def load_failure_analysis(analysis_file):
    with open(analysis_file) as f:
        return json.load(f)

def propose_patches(analysis):
    suggestions = analysis.get("suggestions", [])
    proposals = []

    for s in suggestions:
        failure_type = s.get("failure_type", "")
        template = PATCH_TEMPLATES.get(failure_type)

        proposal = {
            "failure_type": failure_type,
            "count": s.get("count", 0),
            "affected_cases": s.get("affected_cases", []),
            "fix_area": s.get("fix_area", ""),
            "priority": "P0" if s.get("count", 0) >= 3 else ("P1" if s.get("count", 0) >= 2 else "P2"),
            "suggestion": s.get("suggestion", ""),
            "template": template
        }
        proposals.append(proposal)

    return sorted(proposals, key=lambda p: p["count"], reverse=True)

def generate_patch_document(proposals, output_path):
    lines = []
    lines.append("# KDNA Lab — Patch Proposals")
    lines.append(f"")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Proposals:** {len(proposals)}")
    lines.append("")

    for i, p in enumerate(proposals):
        template = p.get("template")
        lines.append(f"## Proposal {i+1}: {p['failure_type']}")
        lines.append("")
        lines.append(f"**Priority:** {p['priority']} | **Affected cases:** {p['count']} | **Area:** {p['fix_area']}")
        lines.append("")
        lines.append(f"**Problem:** {p['suggestion']}")
        lines.append("")

        if template:
            lines.append(f"**Action:** `{template.get('action', 'N/A')}`")
            lines.append(f"**Target file:** `{template.get('target_file', 'N/A')}`")
            lines.append(f"**Description:** {template.get('description', 'N/A')}")
            lines.append("")
            lines.append("**Example change:**")
            lines.append("```json")
            lines.append(json.dumps(template.get("example_change", {}), indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")
            lines.append("**Regression tests to add:**")
            for test in template.get("regression_tests", []):
                lines.append(f"- {test}")
        else:
            lines.append("No template available. Manual investigation needed.")
        lines.append("")

        lines.append(f"**Affected cases:** {', '.join(p['affected_cases'])}")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KDNA Lab Patch Proposer")
    parser.add_argument("analysis_file", nargs="?", help="Failure analysis JSON file")
    parser.add_argument("--output", default=None, help="Output path for patch document")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.analysis_file:
        # Try default path
        failures_dir = LAB_ROOT / "outputs" / "failures"
        files = list(failures_dir.glob("*.json"))
        if files:
            args.analysis_file = str(sorted(files)[-1])
            print(f"[INFO] Using latest analysis: {args.analysis_file}")
        else:
            print("[ERROR] No failure analysis file found. Run failure_classifier.py first.")
            return

    analysis = load_failure_analysis(args.analysis_file)
    proposals = propose_patches(analysis)
    print(f"[INFO] Generated {len(proposals)} patch proposals")

    if args.json:
        print(json.dumps(proposals, indent=2, ensure_ascii=False))
    else:
        output_path = args.output or str(LAB_ROOT / "reports" / f"patch_proposals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        path = generate_patch_document(proposals, output_path)
        print(f"[INFO] Patch document → {path}")

        print(f"\nSummary:")
        for p in proposals:
            template = p.get("template")
            action = template.get("action", "manual") if template else "manual"
            print(f"  [{p['priority']}] {p['failure_type']} ({p['count']}x) → {action} in {p['fix_area']}")

if __name__ == "__main__":
    main()
