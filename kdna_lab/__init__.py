"""
KDNA Lab — KDNA ecosystem experimental infrastructure.

Public API for case loading, rule checks, scoring, reporting,
and experiment runners.
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

__version__ = "2026.05.28"
__all__ = [
    "load_cases",
    "load_cases_list",
    "check_must_include",
    "check_must_not_include",
    "check_json_valid",
    "check_character_count",
    "load_config",
    "resolve_output_dir",
    "find_outputs",
    "extract_output_body",
    "resolve_lab_root",
    "LAB_ROOT",
]
