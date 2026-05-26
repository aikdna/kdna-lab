"""Path resolution and environment configuration for KDNA Lab."""

import os
from pathlib import Path


def resolve_lab_root() -> Path:
    """Resolve the KDNA Lab root directory.

    Priority:
    1. KDNA_LAB_ROOT environment variable
    2. Default: parent of the directory containing this file
    """
    env_root = os.environ.get("KDNA_LAB_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


LAB_ROOT = resolve_lab_root()
