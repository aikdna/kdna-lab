"""L1 hard-check implementations for KDNA Lab scoring."""

import json
import re
from typing import List, Tuple


NEGATION_PATTERNS = [
    "不是", "并非", "而非", "而不是", "不算是", "不能算", "不等于",
    "not ", "is not ", "are not ", "isn't ", "aren't ", "rather than",
    "不是...而是", "不是...是"
]


def check_must_include(output: str, must_include: List[str]) -> Tuple[bool, List[dict]]:
    """Check if all required phrases appear in the output."""
    results = []
    all_passed = True
    for item in must_include:
        found = item.lower() in output.lower()
        results.append({"item": item, "found": found})
        if not found:
            all_passed = False
    return all_passed, results


def _is_in_negation_context(text: str, term: str, window: int = 40) -> bool:
    """Check if a term appears in a negation context (case-insensitive)."""
    text_lower = text.lower()
    term_lower = term.lower()
    idx = text_lower.find(term_lower)
    if idx == -1:
        return False
    context = text_lower[max(0, idx - window):idx]
    for pat in NEGATION_PATTERNS:
        if pat in context:
            return True
    return False


def check_must_not_include(output: str, must_not_include: List[str]) -> Tuple[bool, List[str]]:
    """Check if any banned phrases appear in the output (allowing negated usage)."""
    violations = []
    all_clean = True
    output_lower = output.lower()
    for item in must_not_include:
        if item.lower() in output_lower:
            if _is_in_negation_context(output, item):
                continue
            violations.append(item)
            all_clean = False
    return all_clean, violations


def check_json_valid(output: str) -> Tuple[bool, str]:
    """Validate JSON presence and parsability in output."""
    json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
    if json_match:
        try:
            json.loads(json_match.group(1))
            return True, "valid (code block)"
        except json.JSONDecodeError as e:
            return False, f"invalid JSON in code block: {e}"
    if output.strip().startswith("{"):
        try:
            json.loads(output.strip())
            return True, "valid (raw)"
        except json.JSONDecodeError:
            pass
    return False, "no JSON found in output (JSON was required)"


def check_character_count(output: str, max_chars: int = None) -> Tuple[bool, int, int]:
    """Check if output length is within character limit."""
    actual = len(output)
    if max_chars and actual > max_chars:
        return False, actual, max_chars
    return True, actual, max_chars
