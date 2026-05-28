#!/usr/bin/env python3
"""KDNA Lab — Rule Scorer (thin wrapper).

This script is a convenience wrapper. The main implementation is in kdna_lab.rule_scorer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kdna_lab.rule_scorer import score_cli

if __name__ == "__main__":
    score_cli()
