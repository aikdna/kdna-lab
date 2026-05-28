#!/usr/bin/env python3
"""KDNA Lab — CLI Case Runner (thin wrapper).

This script is a convenience wrapper. The main implementation is in kdna_lab.cli_runner.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kdna_lab.cli_runner import run_cli_cases_cli

if __name__ == "__main__":
    run_cli_cases_cli()
