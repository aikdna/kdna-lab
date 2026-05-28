"""Case loading utilities for JSONL case files."""

import json
from typing import Dict, List


def load_cases(case_file: str) -> Dict[str, dict]:
    """Load cases from a JSONL file into a dict keyed by case id."""
    cases = {}
    with open(case_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num} of {case_file}: {e}") from e
            case_id = c.get("id")
            if not case_id:
                raise KeyError(f"Missing 'id' field on line {line_num} of {case_file}")
            if case_id in cases:
                print(f"[WARN] Duplicate case ID '{case_id}' on line {line_num}, overwriting previous.", flush=True)
            cases[case_id] = c
    return cases


def load_cases_list(case_file: str) -> List[dict]:
    """Load cases from a JSONL file into a list preserving order."""
    cases = []
    with open(case_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num} of {case_file}: {e}") from e
    return cases
