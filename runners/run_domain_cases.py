#!/usr/bin/env python3
"""KDNA Lab — Domain Case Runner (thin wrapper).

This script is a convenience wrapper. The main implementation is in kdna_lab.domain_runner.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kdna_lab.domain_runner import run_domain_cases_cli

if __name__ == "__main__":
    run_domain_cases_cli()
