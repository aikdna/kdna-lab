"""Case loading utilities for JSONL case files."""

import json
from typing import Dict, List


def load_cases(case_file: str) -> Dict[str, dict]:
    """Load cases from a JSONL file into a dict keyed by case id."""
    cases = {}
    with open(case_file) as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                cases[c["id"]] = c
    return cases


def load_cases_list(case_file: str) -> List[dict]:
    """Load cases from a JSONL file into a list preserving order."""
    cases = []
    with open(case_file) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases
