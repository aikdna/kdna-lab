"""Tests for KDNA Lab core library."""

import json
import multiprocessing
import sys
import tempfile
import time
import types
from pathlib import Path

import pytest

from kdna_lab.cases import load_cases, load_cases_list
from kdna_lab.checks import (
    check_must_include,
    check_must_not_include,
    check_json_valid,
    check_character_count,
    _is_in_negation_context,
)
from kdna_lab.outputs import find_outputs
from kdna_lab.runner import ExperimentRunner
from kdna_lab.domain_runner import DomainRunner
from kdna_lab.scoring_pipeline import ScoringPipeline, pipeline_cli


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


class TestBenchmarkArtifacts:
    def test_domain_runner_prefers_configured_conditions(self):
        runner = DomainRunner(Path("/tmp"), {
            "runners": {
                "domain": {
                    "conditions": ["no_kdna", "best_prompt", "kdna_full"]
                }
            }
        })
        case = {"id": "case-1", "input": "test", "conditions": ["kdna_full"]}
        assert runner._conditions_for_case(case) == ["no_kdna", "best_prompt", "kdna_full"]

    def test_domain_runner_uses_case_conditions_without_config_override(self):
        runner = DomainRunner(Path("/tmp"), {"runners": {"domain": {}}})
        case = {"id": "case-1", "input": "test", "conditions": ["kdna_full"]}
        assert runner._conditions_for_case(case) == ["kdna_full"]

    def test_domain_runner_records_failed_provider_call_in_artifact(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            runner = DomainRunner(Path(tmp), {
                "domain": {"name": "@aikdna/writing"},
                "output": {"dir": str(Path(tmp) / "outputs")},
                "runners": {
                    "domain": {
                        "conditions": ["kdna_full"],
                        "rate_limit": 0,
                    }
                },
            })
            monkeypatch.setattr(runner, "load_domain_prompt", lambda domain: "domain prompt")
            monkeypatch.setattr(runner, "_load_domain_metadata", lambda domain: {})
            monkeypatch.setattr(runner, "call_api", lambda prompt: None)

            results = runner.run_all([{"id": "case-1", "input": "test"}])

            assert len(results) == 1
            assert results[0]["error"] == "provider_call_failed_or_timed_out"

            artifacts = list((Path(tmp) / "outputs" / "raw").glob("*benchmark-run-v1.raw.json"))
            assert len(artifacts) == 1
            artifact = json.loads(artifacts[0].read_text())
            assert artifact["cases"][0]["case_id"] == "case-1"
            assert artifact["cases"][0]["error"] == "provider_call_failed_or_timed_out"

    def test_runner_passes_timeout_to_provider(self, monkeypatch):
        captured = {}

        def fake_call_provider_with_timeout(call_kwargs, timeout):
            captured.update(call_kwargs)
            captured["hard_timeout"] = timeout
            return "ok"

        runner = ExperimentRunner(Path("/tmp"), {
            "api": {
                "provider": "openai_compatible",
                "model": "test-model",
                "base_url": "http://example.invalid",
                "api_key_env": "MISSING_KEY",
                "timeout": 17,
            }
        })
        monkeypatch.setattr(runner, "_call_provider_with_timeout", fake_call_provider_with_timeout)

        assert runner.call_api("prompt") == "ok"
        assert captured["timeout"] == 17
        assert captured["hard_timeout"] == 17

    def test_runner_enforces_hard_provider_timeout(self, monkeypatch):
        if "fork" not in multiprocessing.get_all_start_methods():
            pytest.skip("hard timeout monkeypatch test requires fork start method")

        def fake_call_provider(**kwargs):
            time.sleep(1)
            return "late"

        monkeypatch.setattr("kdna_lab.providers.call_provider", fake_call_provider)
        runner = ExperimentRunner(Path("/tmp"), {})
        call_kwargs = {
            "provider_name": "openai_compatible",
            "prompt": "prompt",
            "model": "test-model",
        }

        started = time.monotonic()
        result = runner._call_provider_with_timeout(call_kwargs, 0.05)

        assert result is None
        assert time.monotonic() - started < 0.5

    def test_save_output_isolates_conditions(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ExperimentRunner(Path(tmp), {"output": {"dir": str(Path(tmp) / "outputs")}})
            runner.run_id = "run_test"

            no_kdna = runner.save_output(
                "case-1",
                "generic output",
                Condition="no_kdna",
                Provider="test-provider",
                Model="test-model",
            )
            kdna = runner.save_output(
                "case-1",
                "kdna output",
                Condition="kdna_full",
                Provider="test-provider",
                Model="test-model",
            )

            assert no_kdna != kdna
            assert Path(no_kdna).exists()
            assert Path(kdna).exists()
            assert "no_kdna" in Path(no_kdna).name
            assert "kdna_full" in Path(kdna).name

            outputs = find_outputs(str(Path(tmp) / "outputs"))
            assert "case-1" in outputs
            conditions = {o.get("condition") for o in outputs["case-1"]}
            assert conditions == {"no_kdna", "kdna_full"}

    def test_find_outputs_reads_benchmark_run_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            artifact = {
                "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
                "run_id": "run_test",
                "domain": "@aikdna/writing",
                "provider": "test-provider",
                "model": "test-model",
                "case_count": 1,
                "conditions": ["kdna_full"],
                "cases": [
                    {
                        "case_id": "case-1",
                        "condition": "kdna_full",
                        "output": "diagnose structure first",
                        "scores": {},
                    }
                ],
            }
            (raw / "run_test_benchmark-run-v1.raw.json").write_text(json.dumps(artifact))

            outputs = find_outputs(tmp)
            assert outputs["case-1"][0]["condition"] == "kdna_full"
            assert outputs["case-1"][0]["content"] == "diagnose structure first"

    def test_find_outputs_prefers_benchmark_run_json_over_domain_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            (raw / "run_test_case-1_kdna_full.txt").write_text(
                "# Case: case-1\n# Condition: kdna_full\n---\nlegacy txt output"
            )
            artifact = {
                "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
                "run_id": "run_test",
                "domain": "@aikdna/writing",
                "provider": "test-provider",
                "model": "test-model",
                "case_count": 1,
                "conditions": ["kdna_full"],
                "cases": [
                    {
                        "case_id": "case-1",
                        "condition": "kdna_full",
                        "output": "structured output",
                        "scores": {},
                    }
                ],
            }
            (raw / "run_test_benchmark-run-v1.raw.json").write_text(json.dumps(artifact))

            outputs = find_outputs(tmp)
            assert len(outputs["case-1"]) == 1
            assert outputs["case-1"][0]["content"] == "structured output"

    def test_find_outputs_ignores_scored_benchmark_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            raw_artifact = {
                "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
                "run_id": "run_test",
                "domain": "@aikdna/writing",
                "provider": "test-provider",
                "model": "test-model",
                "case_count": 1,
                "conditions": ["kdna_full"],
                "cases": [
                    {
                        "case_id": "case-1",
                        "condition": "kdna_full",
                        "output": "raw output",
                        "scores": {},
                    }
                ],
                "status": "raw",
            }
            scored_artifact = dict(raw_artifact)
            scored_artifact["run_id"] = "pipeline_test"
            scored_artifact["status"] = "scored"
            scored_artifact["cases"] = [
                {
                    "case_id": "case-1",
                    "condition": "kdna_full",
                    "output": "scored output",
                    "scores": {"L1": {"passed": True}},
                }
            ]
            (raw / "run_test_benchmark-run-v1.raw.json").write_text(json.dumps(raw_artifact))
            (raw / "pipeline_test_benchmark-run-v1.scored.json").write_text(json.dumps(scored_artifact))

            outputs = find_outputs(tmp)
            assert len(outputs["case-1"]) == 1
            assert outputs["case-1"][0]["content"] == "raw output"

    def test_scoring_pipeline_emits_scored_benchmark_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs"
            raw = output_dir / "raw"
            raw.mkdir(parents=True)
            case_file = root / "cases.jsonl"
            case_file.write_text(
                json.dumps({
                    "id": "case-1",
                    "target": "@aikdna/writing",
                    "input": "review this",
                    "must_include": ["structure"],
                    "must_not_include": ["grammar"],
                }) + "\n"
            )
            artifact = {
                "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
                "run_id": "run_test",
                "domain": "@aikdna/writing",
                "provider": "test-provider",
                "model": "test-model",
                "case_count": 1,
                "conditions": ["kdna_full"],
                "cases": [
                    {
                        "case_id": "case-1",
                        "condition": "kdna_full",
                        "output": "The structure is missing a clear argument.",
                        "scores": {},
                    }
                ],
            }
            (raw / "run_test_benchmark-run-v1.raw.json").write_text(json.dumps(artifact))

            pipeline = ScoringPipeline(root)
            result = pipeline.run(
                str(case_file),
                str(output_dir),
                l2_judge=lambda case, body, cfg: {
                    "scores": {"judgment_path": 3},
                    "total": 3,
                    "max_total": 3,
                    "passed": True,
                },
                run_id="pipeline_test",
            )

            assert result["L2"]["total"] == 1
            assert result["results"][0]["L2_score"]["passed"] is True
            scored = Path(result["benchmark_run_artifact"])
            assert scored.exists()
            scored_payload = json.loads(scored.read_text())
            assert scored_payload["cases"][0]["scores"]["L2"]["passed"] is True

    def test_pipeline_cli_l2_flag_assigns_judge(self, monkeypatch, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs"
            raw = output_dir / "raw"
            raw.mkdir(parents=True)
            case_file = root / "cases.jsonl"
            case_file.write_text(
                json.dumps({
                    "id": "case-1",
                    "target": "@aikdna/writing",
                    "input": "review this",
                    "must_include": ["structure"],
                    "must_not_include": [],
                }) + "\n"
            )
            artifact = {
                "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
                "run_id": "run_test",
                "domain": "@aikdna/writing",
                "provider": "test-provider",
                "model": "test-model",
                "case_count": 1,
                "conditions": ["kdna_full"],
                "cases": [
                    {
                        "case_id": "case-1",
                        "condition": "kdna_full",
                        "output": "structure",
                        "scores": {},
                    }
                ],
            }
            (raw / "run_test_benchmark-run-v1.raw.json").write_text(json.dumps(artifact))

            internal_lib = types.ModuleType("internal_lib")
            llm_client = types.ModuleType("internal_lib.llm_client")
            llm_client.call_llm = lambda *args, **kwargs: "ok"
            config = types.ModuleType("internal_lib.config")
            config.load_config = lambda lab_root: {}
            scorer = types.ModuleType("kdna_lab_internal_scorers_llm_judge")
            scorer.score_case = lambda case, body, cfg: {
                "scores": {"judgment_path": 3},
                "total": 3,
                "max_total": 3,
                "passed": True,
            }
            monkeypatch.setitem(sys.modules, "internal_lib", internal_lib)
            monkeypatch.setitem(sys.modules, "internal_lib.llm_client", llm_client)
            monkeypatch.setitem(sys.modules, "internal_lib.config", config)
            monkeypatch.setitem(sys.modules, "kdna_lab_internal_scorers_llm_judge", scorer)
            monkeypatch.setattr(
                sys,
                "argv",
                [
                    "kdna-lab-pipeline",
                    "run",
                    "--case-file",
                    str(case_file),
                    "--output-dir",
                    str(output_dir),
                    "--l2",
                ],
            )

            pipeline_cli()
            captured = capsys.readouterr()
            assert "L2: 1/1" in captured.out
