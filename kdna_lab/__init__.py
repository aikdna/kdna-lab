"""
KDNA Lab — KDNA ecosystem experimental infrastructure.

Public API for case loading, rule checks, scoring, reporting,
experiment runners, and ecosystem validation.
"""

from kdna_lab.cases import load_cases, load_cases_list
from kdna_lab.checks import (
    check_must_include,
    check_must_not_include,
    check_json_valid,
    check_character_count,
)
from kdna_lab.config import load_config, resolve_output_dir
from kdna_lab.outputs import find_outputs, extract_output_body
from kdna_lab.paths import resolve_lab_root, LAB_ROOT

# Runners
from kdna_lab.runner import ExperimentRunner
from kdna_lab.domain_runner import DomainRunner, run_domain_cases
from kdna_lab.cli_runner import CLIRunner, run_cli_cases, run_cli_command, substitute_fixture

# Scoring
from kdna_lab.rule_scorer import score_case, score_all
from kdna_lab.scoring_pipeline import ScoringPipeline, record_human_review

# Reporting
from kdna_lab.report import (
    generate_l1_report,
    generate_domain_report,
    generate_cli_report,
    generate_cross_model_report,
    generate_paper_tables,
    generate_comparison_report,
)

# Ecosystem validation
from kdna_lab.registry_check import check_registry
from kdna_lab.schema_check import (
    resolve_schema_dir,
    validate_domain_directory,
    validate_all_fixtures,
)
from kdna_lab.spec_check import run_spec_check, verify_app_runtime_contract

# Evidence
from kdna_lab.evidence_store import EvidenceStore

# Portability
from kdna_lab.portability_check import (
    AGENT_PROFILES,
    PortabilityRunner,
    analyze_portability,
    run_portability_test,
)

# Quality
from kdna_lab.badge_check import BadgeChecker, BADGE_LEVELS

# Evolution
from kdna_lab.evolution_tracker import (
    create_evolution_record,
    apply_human_lock,
    record_regression_results,
)

__version__ = "2026.05.28"
