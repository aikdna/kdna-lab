"""Output discovery and parsing utilities."""

import json
from pathlib import Path
from typing import Dict, List


def find_outputs(output_dir: str) -> Dict[str, List[dict]]:
    """Discover and classify output files in a directory.

    Returns a dict keyed by case_id, where each value is a list of
    output info dicts with keys: file, case_id, content, type.
    """
    outputs = {}
    raw_dir = Path(output_dir) / "raw"
    if not raw_dir.exists():
        return outputs

    for f in raw_dir.glob("*.txt"):
        if "_prompt" in f.stem:
            continue
        content = f.read_text()
        lines = content.split("\n")
        case_id = f.stem
        for line in lines[:15]:
            if line.startswith("# Case:"):
                case_id = line.replace("# Case:", "").strip()
                break
        key = case_id
        if key not in outputs:
            outputs[key] = []
        outputs[key].append({"file": str(f), "case_id": case_id, "content": content, "type": "domain"})

    for f in raw_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "exit_code" in data and "stdout" in data:
            case_id = data.get("case_id", f.stem)
            combined = data.get("stdout", "") + "\n" + data.get("stderr", "")
            key = case_id
            if key not in outputs:
                outputs[key] = []
            outputs[key].append({"file": str(f), "case_id": case_id, "content": combined, "type": "cli"})
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "exit_code" in item:
                    cid = item.get("case_id", f.stem)
                    combined = item.get("stdout", "") + "\n" + item.get("stderr", "")
                    key = cid
                    if key not in outputs:
                        outputs[key] = []
                    outputs[key].append({"file": str(f), "case_id": cid, "content": combined, "type": "cli"})

    return outputs


def extract_output_body(content: str) -> str:
    """Extract the actual response from a marked-up output file.

    Looks for a '---' separator and returns everything after it.
    Falls back to the full content if no separator is found.
    """
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        body = content
    return body
