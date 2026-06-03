# @aikdna/prompt_diagnosis Benchmark Run — 2026-06-03

This directory contains a structured KDNA Lab benchmark artifact for
`@aikdna/prompt_diagnosis` under the v1.0-rc public-confidence workstream.

This is **not** a validated badge claim. It is a release-evidence checkpoint
that preserves raw outputs, scored outputs, and provider timeout failures.

## Run

| Field | Value |
| --- | --- |
| Domain | `@aikdna/prompt_diagnosis` |
| Case file | `examples/prompt_diagnosis/cases.jsonl` |
| Cases | 30 |
| Conditions | `no_kdna`, `best_prompt`, `kdna_full` |
| Provider | `openai_compatible` |
| Model | `deepseek-ai/DeepSeek-V4-Pro` |
| Raw run | `run_20260603_160454` |
| Scored run | `pipeline_20260603_171144` |

## Artifacts

| Artifact | Purpose |
| --- | --- |
| `benchmark-run-v1.raw.json` | Raw benchmark outputs and provider failure markers |
| `benchmark-run-v1.scored.json` | L1 scored benchmark artifact preserving failure causes |

## Results

| Condition | Outputs | L1 pass | Provider timeout errors |
| --- | ---: | ---: | ---: |
| `no_kdna` | 30 | 1 | 9 |
| `best_prompt` | 30 | 2 | 9 |
| `kdna_full` | 30 | 0 | 2 |
| Total | 90 | 3 | 20 |

## Interpretation

- The artifact pipeline preserved 90 condition-isolated records, including 20
  provider timeout failures.
- The low L1 pass rate means this run should be treated as diagnostic evidence,
  not proof of domain validation.
- `@aikdna/prompt_diagnosis` must remain below `validated` until rubric
  calibration, L2 scoring, human review, limitations, regression comparison,
  and signed release asset updates are complete.
