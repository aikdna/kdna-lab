"""Shared config loading and output directory resolution for KDNA Lab."""

import os
from pathlib import Path
from typing import Any, Dict


def load_config(lab_root: Path, config_path: Path | None = None) -> Dict[str, Any]:
    """Load config from YAML file, returning defaults if not found."""
    if config_path and config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)

    default_path = lab_root / "configs" / "default.yaml"
    if default_path.exists():
        import yaml
        with open(default_path) as f:
            return yaml.safe_load(f)

    return _default_config(lab_root)


def _default_config(lab_root: Path) -> Dict[str, Any]:
    return {
        "api": {"provider": "openai", "model": "gpt-4o", "base_url": None, "api_key_env": "OPENAI_API_KEY"},
        "output": {"dir": str(lab_root / "outputs")},
        "domain": {"name": "@aikdna/kdna_propagation", "load_cmd": "kdna load", "format": "prompt"},
        "runners": {"cli": {"timeout": 30}},
    }


def resolve_output_dir(config: dict, lab_root: Path) -> str:
    output_dir = config.get("output", {}).get("dir", "outputs")
    if not os.path.isabs(output_dir):
        output_dir = str(lab_root / output_dir)
    return output_dir
