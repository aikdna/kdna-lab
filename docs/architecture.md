# KDNA Lab Architecture

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    KDNA Lab System                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Experiment   │  │ Case Store   │  │ Fixture Store │ │
│  │ Registry     │  │ (JSONL)      │  │ (domains/     │ │
│  │ (YAML)       │  │              │  │  snapshots)   │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘ │
│         │                 │                   │         │
│         └─────────┬───────┴───────────────────┘         │
│                   ▼                                      │
│  ┌──────────────────────────────────────┐               │
│  │              Runner                   │               │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐ │               │
│  │  │CLI      │ │Agent   │ │Model    │ │               │
│  │  │Runner   │ │Runner  │ │Runner   │ │               │
│  │  └─────────┘ └────────┘ └─────────┘ │               │
│  │  ┌─────────┐ ┌────────┐             │               │
│  │  │Registry │ │Product │             │               │
│  │  │Runner   │ │Runner  │             │               │
│  │  └─────────┘ └────────┘             │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │           Scorer / Judge              │               │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐ │               │
│  │  │L1 Rule  │ │L2 LLM  │ │L3 Human │ │               │
│  │  │Scorer   │ │Judge   │ │Audit    │ │               │
│  │  └─────────┘ └────────┘ └─────────┘ │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │         Failure Analyzer              │               │
│  │  classify → cluster → suggest fix    │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │         Patch Proposer                │               │
│  │  propose → regress → human review    │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │         Report Generator              │               │
│  │  domain / CLI / security / paper     │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │          Evidence Store               │               │
│  │  raw / traces / scores / failures    │               │
│  │  patches / reviews / releases        │               │
│  └──────────────────────────────────────┘               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 数据流

```
Case Definition (JSONL)
    │
    ▼
Experiment Registry (YAML)
    │  experiment_id, target, hypothesis, metrics
    ▼
Runner
    │  条件: No KDNA / Best Prompt / KDNA Full / KDNA Compact
    │  环境: os, cli_version, agent, model
    ▼
Raw Output
    │  stdout, stderr, exit_code, trace, artifacts
    ▼
Scorer
    │  L1: rule-based (pass/fail)
    │  L2: LLM judge (rubric score)
    │  L3: human audit
    ▼
Scored Output + Failure Tags
    │
    ▼
Failure Analyzer
    │  classify failure type
    │  cluster similar failures
    │  suggest root cause
    ▼
Patch Proposer (optional)
    │  propose fix
    │  run regression
    ▼
Report Generator
    │  domain_test_report.md
    │  cli_regression_report.md
    │  cross_model_report.md
    ▼
Evidence Store
    │  permanent archive
    ▼
Roadmap / Issue / Paper
```

## 模块职责

### Experiment Registry

- 所有实验的目录（YAML 定义）
- 每个实验声明：id, area, target, hypothesis, input, expected, metrics
- 支持按 area/priority/target 筛选

### Case Store

- 测试案例的批量存储（JSONL 格式）
- 每个 case 有：id, input, expected_behavior, must_include, must_not_include, rubric
- 按 domain/cli/schema 等分类

### Runner

- 执行实验并收集原始输出
- 支持多 runner：CLI Runner, Agent Runner, Model Runner, Registry Runner, Product Runner
- 保存完整环境元数据

### Scorer

- L1 Hard Checks：must_include 命中率、must_not_include 零命中、exit code、JSON 合法性
- L2 Rubric Checks：LLM judge 按 rubric 评分
- L3 Human Audit：人类最终审查

### Failure Analyzer

- 失败分类：schema_doc_mismatch, cli_error_unclear, canonical_phrase_missing, banned_claim_leak, fact_fabrication 等
- 聚类相似失败
- 生成修复建议

### Patch Proposer

- 基于失败分析生成修复方案
- 自动运行回归测试
- 提交人类审查

### Report Generator

- 多类型报告模板
- Markdown 输出，可直接用于 GitHub Issues 或论文

### Evidence Store

- 所有实验数据的长期归档
- 目录结构：raw_outputs/, traces/, reports/, scores/, failures/, patches/, human_reviews/, releases/
