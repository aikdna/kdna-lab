"""Tests for KDNA Lab core library."""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.cases import load_cases, load_cases_list
from lib.checks import (
    check_must_include,
    check_must_not_include,
    check_json_valid,
    check_character_count,
    _is_in_negation_context,
)


class TestCases:
    def test_load_cases_list_basic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": "case1", "input": "test1"}\n')
            f.write('{"id": "case2", "input": "test2"}\n')
            tmp = f.name
        try:
            cases = load_cases_list(tmp)
            assert len(cases) == 2
            assert cases[0]["id"] == "case1"
            assert cases[1]["id"] == "case2"
        finally:
            Path(tmp).unlink()

    def test_load_cases_list_empty_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('\n')
            f.write('{"id": "case1", "input": "test1"}\n')
            f.write('\n')
            f.write('\n')
            tmp = f.name
        try:
            cases = load_cases_list(tmp)
            assert len(cases) == 1
        finally:
            Path(tmp).unlink()

    def test_load_cases_list_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": "case1", "input": "test1"}\n')
            f.write('not valid json\n')
            tmp = f.name
        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_cases_list(tmp)
        finally:
            Path(tmp).unlink()

    def test_load_cases_duplicate_warning(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": "case1", "input": "first"}\n')
            f.write('{"id": "case1", "input": "second"}\n')
            tmp = f.name
        try:
            cases = load_cases(tmp)
            captured = capsys.readouterr()
            assert "[WARN] Duplicate case ID" in captured.out
            assert cases["case1"]["input"] == "second"
        finally:
            Path(tmp).unlink()

    def test_load_cases_missing_id(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"no_id": true}\n')
            tmp = f.name
        try:
            with pytest.raises(KeyError, match="Missing 'id'"):
                load_cases(tmp)
        finally:
            Path(tmp).unlink()


class TestMustInclude:
    def test_all_found(self):
        passed, results = check_must_include("hello world", ["hello", "world"])
        assert passed is True
        assert len(results) == 2

    def test_some_missing(self):
        passed, results = check_must_include("hello world", ["hello", "goodbye"])
        assert passed is False
        missing = [r["item"] for r in results if not r["found"]]
        assert "goodbye" in missing

    def test_case_insensitive(self):
        passed, results = check_must_include("Hello World", ["hello", "world"])
        assert passed is True


class TestMustNotInclude:
    def test_no_violations(self):
        passed, violations = check_must_not_include("clean text", ["bad"])
        assert passed is True
        assert violations == []

    def test_with_violations(self):
        passed, violations = check_must_not_include("this has bad word", ["bad"])
        assert passed is False
        assert "bad" in violations

    def test_negated_context_allowed(self):
        passed, violations = check_must_not_include(
            "KDNA不是万能工具，而是精确工具",
            ["万能工具"]
        )
        assert passed is True

    def test_negated_context_english(self):
        passed, violations = check_must_not_include(
            "This is not a guarantee but rather a guide",
            ["guarantee"]
        )
        assert passed is True

    def test_negation_only_first_occurrence(self):
        """Regression test: ensure all occurrences are checked, not just the first."""
        passed, violations = check_must_not_include(
            "This is not leaking. But leaking is bad.",
            ["leaking"]
        )
        assert passed is False
        assert "leaking" in violations


class TestJsonCheck:
    def test_valid_code_block(self):
        passed, detail = check_json_valid('```json\n{"key": "value"}\n```')
        assert passed is True
        assert "code block" in detail

    def test_invalid_code_block(self):
        passed, detail = check_json_valid('```json\n{invalid}\n```')
        assert passed is False

    def test_valid_raw(self):
        passed, detail = check_json_valid('{"key": "value"}')
        assert passed is True

    def test_no_json(self):
        passed, detail = check_json_valid("just some text")
        assert passed is False


class TestCharacterCount:
    def test_within_limit(self):
        passed, actual, max_chars = check_character_count("hello", max_chars=100)
        assert passed is True
        assert actual == 5
        assert max_chars == 100

    def test_exceeds_limit(self):
        passed, actual, max_chars = check_character_count("hello", max_chars=3)
        assert passed is False
        assert actual == 5

    def test_no_limit(self):
        passed, actual, max_chars = check_character_count("hello")
        assert passed is True
        assert max_chars is None
