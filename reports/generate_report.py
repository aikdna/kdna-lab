#!/usr/bin/env python3
"""KDNA Lab — Report Generator (thin wrapper).

This script is a convenience wrapper. The main implementation is in kdna_lab.report.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kdna_lab.report import report_cli

if __name__ == "__main__":
    report_cli()
