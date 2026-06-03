"""Output discovery and parsing utilities."""

import json
from pathlib import Path
from typing import Dict, List, Tuple


def _append_output(outputs: Dict[str, List[dict]], case_id: str, info: dict) -> None:
    outputs.setdefault(case_id, []).append(info)


def _load_benchmark_run_json(path: Path) -> List[Tuple[str, dict]]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or "cases" not in data:
        return []
    rows = []
    for item in data.get("cases", []):
        if not isinstance(item, dict):
            continue
        case_id = item.get("case_id")
        if not case_id:
            continue
        rows.append((case_id, {
            "file": str(path),
            "case_id": case_id,
            "condition": item.get("condition"),
            "content": item.get("output", ""),
            "type": "domain",
            "benchmark_run": data.get("run_id"),
            "scores": item.get("scores", {}),
        }))
    return rows


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
        condition = None
        for line in lines[:15]:
            if line.startswith("# Case:"):
                case_id = line.replace("# Case:", "").strip()
            elif line.startswith("# Condition:"):
                condition = line.replace("# Condition:", "").strip()
        _append_output(outputs, case_id, {
            "file": str(f),
            "case_id": case_id,
            "condition": condition,
            "content": content,
            "type": "domain",
        })

    for f in raw_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("schema") == "https://aikdna.com/schemas/benchmark-run-v1.json":
            for cid, info in _load_benchmark_run_json(f):
                _append_output(outputs, cid, info)
            continue
        if isinstance(data, dict) and "exit_code" in data and "stdout" in data:
            case_id = data.get("case_id", f.stem)
            combined = data.get("stdout", "") + "\n" + data.get("stderr", "")
            _append_output(outputs, case_id, {"file": str(f), "case_id": case_id, "content": combined, "type": "cli"})
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "exit_code" in item:
                    cid = item.get("case_id", f.stem)
                    combined = item.get("stdout", "") + "\n" + item.get("stderr", "")
                    _append_output(outputs, cid, {"file": str(f), "case_id": cid, "content": combined, "type": "cli"})

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
