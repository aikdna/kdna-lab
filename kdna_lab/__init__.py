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

# Runtime
from kdna_lab.runtime_check import (
    run_runtime_checks,
    check_route_cases,
    check_match_cases,
    check_select_cases,
    check_load_profiles,
)

# Trace
from kdna_lab.trace_check import check_trace_structure, check_all_traces

# Protocol Version
from kdna_lab.version_check import run_version_matrix

# Multi-Provider
from kdna_lab.providers import (
    PROVIDERS,
    PROVIDER_PRESETS,
    call_provider,
    get_provider,
)

# Work Pack
from kdna_lab.workpack_check import (
    resolve_workpack_dir,
    discover_workpacks,
    validate_workpack_manifest,
    check_workpack_structure,
    run_workpack_checks,
)

__version__ = "2026.05.29"

__all__ = [
    # Cases & Checks
    "load_cases", "load_cases_list",
    "check_must_include", "check_must_not_include",
    "check_json_valid", "check_character_count",
    # Config & Paths
    "load_config", "resolve_output_dir",
    "find_outputs", "extract_output_body",
    "resolve_lab_root", "LAB_ROOT",
    # Runners
    "ExperimentRunner", "DomainRunner", "run_domain_cases",
    "CLIRunner", "run_cli_cases", "run_cli_command", "substitute_fixture",
    # Scoring
    "score_case", "score_all",
    "ScoringPipeline", "record_human_review",
    # Reports
    "generate_l1_report", "generate_domain_report",
    "generate_cli_report", "generate_cross_model_report",
    "generate_paper_tables", "generate_comparison_report",
    # Ecosystem Validation
    "check_registry",
    "resolve_schema_dir", "validate_domain_directory", "validate_all_fixtures",
    "run_spec_check", "verify_app_runtime_contract",
    # Evidence
    "EvidenceStore",
    # Portability
    "AGENT_PROFILES", "PortabilityRunner", "analyze_portability", "run_portability_test",
    # Quality
    "BadgeChecker", "BADGE_LEVELS",
    # Evolution
    "create_evolution_record", "apply_human_lock", "record_regression_results",
    # Runtime
    "run_runtime_checks", "check_route_cases", "check_match_cases",
    "check_select_cases", "check_load_profiles",
    # Trace
    "check_trace_structure", "check_all_traces",
    # Protocol Version
    "run_version_matrix",
    # Multi-Provider
    "PROVIDERS", "PROVIDER_PRESETS", "call_provider", "get_provider",
    # Work Pack
    "resolve_workpack_dir", "discover_workpacks",
    "validate_workpack_manifest", "check_workpack_structure",
    "run_workpack_checks",
]
