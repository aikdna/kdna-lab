# Report Format

KDNA Lab 生成的报告格式规范。

---

## 报告类型

| 类型 | 用途 | 文件名模式 |
|------|------|-----------|
| `domain_test` | 单个 domain 的行为测试报告 | `{domain}_{date}_test_report.md` |
| `cli_regression` | CLI 回归测试报告 | `cli_regression_{date}.md` |
| `schema_validation` | Schema 一致性报告 | `schema_validation_{date}.md` |
| `cross_model` | 跨模型/跨 agent 比较 | `cross_model_{date}.md` |
| `security_redteam` | 安全红队测试报告 | `security_redteam_{date}.md` |
| `registry_integrity` | Registry 完整性报告 | `registry_integrity_{date}.md` |
| `domain_evolution` | Domain 版本演化报告 | `{domain}_evolution_{v1}_to_{v2}.md` |
| `paper_benchmark` | 论文级 benchmark 报告 | `benchmark_{experiment}_{date}.md` |

---

## Domain Test Report 模板

```markdown
# Domain Test Report: {target} {version}

**Date**: {date}
**Runner**: {runner}
**Model**: {model}
**Conditions**: {conditions}

## Summary

| Metric | Value |
|--------|-------|
| Total cases | {total} |
| Passed | {passed} |
| Failed | {failed} |
| Pass rate | {rate}% |
| L1 Score | {l1_score} |
| L2 Average | {l2_avg}/{l2_max} |
| Human review pending | {pending} |

## Failed Cases

### {case_id}

- **Input**: {input}
- **Expected**: {expected_behavior}
- **Actual**: {actual}
- **Failure type**: {failure_type}
- **L1 violations**: {l1_violations}
- **L2 deductions**: {l2_deductions}
- **Suggestion**: {suggestion}

## Detailed Scores

| Case ID | L1 | L2 | L3 | Overall |
|---------|-----|-----|-----|---------|
| {id} | {l1} | {l2} | {l3} | {overall} |

## Cross-Case Analysis

### Common failure patterns
- {pattern_1}
- {pattern_2}

### Strengths
- {strength_1}
- {strength_2}

## Recommendations
1. {rec_1}
2. {rec_2}
```

---

## CLI Regression Report 模板

```markdown
# CLI Regression Report

**Date**: {date}
**CLI Version**: {cli_version}
**OS**: {os}

## Summary

| Command | Cases | Passed | Failed | Rate |
|---------|-------|--------|--------|------|
| validate | {n} | {p} | {f} | {r}% |
| install | {n} | {p} | {f} | {r}% |
| load | {n} | {p} | {f} | {r}% |

## Failed Commands

### {command} — {case_id}

- **Input**: `{input}`
- **Expected exit code**: {expected}
- **Actual exit code**: {actual}
- **stdout**: ```
{stdout}
```
- **stderr**: ```
{stderr}
```
- **Error clarity score**: {score}/5
- **Suggestion**: {suggestion}
```

---

## Cross-Model Report 模板

```markdown
# Cross-Model Test Report: {domain} {version}

**Date**: {date}
**Domain**: {target}

## Model Matrix

| Model | L1 Pass | L2 Score | Canonical Phrase | Banned Claim | JSON Valid |
|-------|---------|----------|------------------|--------------|------------|
| DeepSeek | pass | 9/10 | pass | pass | pass |
| Kimi-K2.6 | pass | 8/10 | partial | pass | pass |
| GPT | pass | 10/10 | pass | pass | pass |

## Consistency Analysis

### Consistent across models
- {item_1}
- {item_2}

### Inconsistent across models
- {item_1} — lost in Kimi
- {item_2} — partial in DeepSeek

## Recommendations
```
```

---

## ExperimentRun 完整数据结构

报告生成时使用的原始数据：

```json
{
  "run_id": "run_20260526_001",
  "experiment_id": "propagation_overclaim_001",
  "area": "domain",
  "target": "@aikdna/kdna_propagation",
  "version": "2026.05",
  "environment": {
    "os": "macOS 15",
    "cli_version": "0.7.x",
    "agent": "Claude Code",
    "model": "Kimi-K2.6"
  },
  "condition": "kdna_full",
  "input": "...",
  "output": "...",
  "trace": {},
  "scores": {
    "L1": {},
    "L2": {},
    "L3": {}
  },
  "failures": [],
  "artifacts": {
    "raw_output_path": "outputs/raw/run_20260526_001.txt",
    "trace_path": "outputs/traces/run_20260526_001.json",
    "report_path": "reports/propagation_20260526_test_report.md"
  }
}
```

---

## benchmark-run-v1 Artifact

Reference-domain validation exports MUST use structured JSON or JSONL. Plain
`.txt` outputs are useful for debugging, but they are not sufficient public
evidence for a `validated` KDNA domain.

Required top-level fields:

```json
{
  "schema": "https://aikdna.com/schemas/benchmark-run-v1.json",
  "run_id": "run_20260603_120000",
  "created_at": "2026-06-03T12:00:00Z",
  "domain": "@aikdna/writing",
  "domain_version": "0.7.3",
  "asset_digest": "sha256:...",
  "provider": "openai_compatible",
  "model": "deepseek/deepseek-v4-pro",
  "conditions": ["no_kdna", "best_prompt", "kdna_full"],
  "case_count": 30,
  "cases": [
    {
      "case_id": "writing_structural_diagnosis_001",
      "condition": "kdna_full",
      "input_hash": "sha256:...",
      "output": "...",
      "scores": {
        "L1": {},
        "L2": {}
      },
      "pass": true
    }
  ],
  "status": "scored"
}
```

Rules:

- `case_id + condition` is the unique output key.
- File names for raw text outputs include `case_id`, `condition`, `provider`,
  and `model`.
- `no_kdna`, `best_prompt`, and `kdna_full` outputs must never overwrite each
  other.
- Public `validated` evidence must include scored artifacts, not raw-only
  artifacts.
