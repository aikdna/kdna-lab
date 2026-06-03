# @aikdna/writing Benchmark Run — 2026-06-03

This directory contains the first public structured KDNA Lab benchmark artifact
for `@aikdna/writing` under the v1.0-rc public-confidence workstream.

This is **not** a validated badge claim. It is a release-evidence checkpoint:
raw outputs, scored outputs, and provider failures are preserved so reviewers
can inspect the result instead of relying on a launch narrative.

## Run

| Field | Value |
| --- | --- |
| Domain | `@aikdna/writing` |
| Case file | `examples/writing/cases.jsonl` |
| Cases | 30 |
| Conditions | `no_kdna`, `best_prompt`, `kdna_full` |
| Provider | `openai_compatible` |
| Model | `deepseek-ai/DeepSeek-V4-Pro` |
| Raw run | `run_20260603_135007` |
| Scored run | `pipeline_20260603_144353` |

## Artifacts

| Artifact | Purpose |
| --- | --- |
| `benchmark-run-v1.raw.json` | Raw benchmark outputs and provider failure markers |
| `benchmark-run-v1.scored.json` | L1 scored benchmark artifact preserving failure causes |

## Results

| Condition | Outputs | L1 pass | Provider timeout errors |
| --- | ---: | ---: | ---: |
| `no_kdna` | 30 | 9 | 4 |
| `best_prompt` | 30 | 6 | 2 |
| `kdna_full` | 30 | 10 | 1 |
| Total | 90 | 25 | 7 |

## Interpretation

- The artifact pipeline is now complete enough to preserve successful outputs,
  timeout failures, condition isolation, raw evidence, and scored evidence.
- The L1 pass rate is low and should not be used as a quality claim.
- `@aikdna/writing` must remain below `validated` until L2 scoring, human
  review, limitations, regression comparison, and signed release asset updates
  are complete.
