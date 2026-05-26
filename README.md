# KDNA Lab

> KDNA 生态的实验基础设施。持续验证、压力测试、驱动进化。

**一句话定位：**

KDNA Lab is the experimental infrastructure for the KDNA ecosystem. It continuously tests whether KDNA domains, CLI tools, runtime contracts, registries, licensing mechanisms, agent integrations, and products behave as intended — across models, agents, and environments.

它的目标不是只生成 benchmark 或论文数据，而是把失败变成结构化证据，持续改进 KDNA 协议和生态。

---

## 核心原则

1. **Evidence over claims** — 不靠口号，靠实验数据。
2. **Failures are first-class assets** — 失败案例不是坏消息，是 KDNA 进化的原料。
3. **AI can propose, humans govern** — AI 可以跑实验、提 patch，但核心判断变更需要人类确认（Human Lock）。
4. **Test the ecosystem, not only the output** — 不仅测答案，还测 SPEC、CLI、domain、registry、license、security、product。
5. **Trace everything** — 每次实验保存输入、输出、trace、score、失败原因和环境元数据。

---

## 进化闭环

```
Hypothesis
→ Experiment Design
→ Run (CLI / Agent / Model / Registry / Product)
→ Score (Rule / LLM Judge / Human Audit)
→ Failure Analysis
→ Patch Proposal
→ Human Review / Human Lock
→ Merge → Regression Test
→ Evidence Store → Report → Roadmap
```

---

## 架构概览

```
KDNA Lab
├── Experiment Registry    — 所有实验的结构化定义
├── Case Store             — 测试案例库（JSONL）
├── Runner                 — 实验执行器（CLI/Agent/Model/Registry/Product）
├── Scorer / Judge         — 三层评分（Rule / LLM / Human）
├── Failure Analyzer       — 失败分类 + 修复建议生成
├── Patch Proposer         — 修复方案生成（SPEC/CLI/Domain/Test/Docs）
├── Report Generator       — 多类型报告（domain/CLI/security/paper）
└── Evidence Store          — 所有实验数据的长期归档
```

---

## 覆盖的实验领域

| # | 领域 | 测试目标 |
|---|------|---------|
| 1 | SPEC / Schema | 协议清晰度、schema 一致性、字段约束可理解性 |
| 2 | CLI | 安装、验证、加载、迁移、自动化可靠性 |
| 3 | Domain Behavior | 判断是否生效（定位、边界、抗误导、跨模型） |
| 4 | Runtime / Trace | routing、trace 完整性、feedback 闭环 |
| 5 | Cross-Model / Cross-Agent | domain 可携带性 |
| 6 | Domain Evolution | feedback → patch → 版本对比 |
| 7 | Registry / 分发 | 安装、版本、签名、yanked/deprecated |
| 8 | License / Marketplace | 授权、解密、撤销、离线、水印 |
| 9 | Security / Red Team | 注入、投毒、绕过、隐私泄露 |
| 10 | Product | KDNAChat / Studio / Work 闭环验证 |

---

## 评分体系

| Level | 类型 | 适合 |
|-------|------|------|
| L1 Hard Checks | 机器规则 | must_include, must_not_include, JSON valid, exit code, signature |
| L2 Rubric Checks | 规则 + LLM Judge | problem_defined, boundary_included, platform_fit |
| L3 Human Review | 人类判断 | 是否真实有价值、是否安全、是否符合 KDNA 哲学 |
| L4 Longitudinal | 趋势指标 | 同类失败是否减少、新版本是否更好 |

---

## MVP 范围

**支持：**
- Domain behavior tests（以 kdna_propagation 为首）
- CLI regression tests
- Schema validation tests
- Rule scoring (L1)
- Markdown report

**MVP 目录：**
```
kdna-lab/
  README.md
  docs/
  examples/
    kdna_propagation_cases.jsonl
    cli_cases.jsonl
    schema_cases.jsonl
  runners/
    run_domain_cases.py
    run_cli_cases.py
  scorers/
    rule_scorer.py
  reports/
    generate_report.py
  outputs/
```

---

## Roadmap

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | Design docs + schema | 🔄 进行中 |
| Phase 1 | MVP: domain + CLI + schema tests | ⏳ |
| Phase 2 | Multi-model / multi-agent matrix | ⏳ |
| Phase 3 | Domain Evolution Loop (failure → patch → regression) | ⏳ |
| Phase 4 | Security / License / Registry experiments | ⏳ |
| Phase 5 | Paper + Public Benchmark | ⏳ |

---

## 与 KDNA 生态的关系

KDNA Lab 不是 KDNA 的替代品或竞争者——它是 KDNA 的**进化引擎**。

```
KDNA Protocol (SPEC)
    ↑ 验证
KDNA Lab ──→ 发现 SPEC 不一致 → 反馈给 SPEC 维护者

KDNA CLI
    ↑ 回归测试
KDNA Lab ──→ 发现 CLI bug → 提 issue/patch

KDNA Domains
    ↑ 行为测试
KDNA Lab ──→ 发现 domain 不守边界 → 生成 domain patch

KDNA Registry
    ↑ 完整性测试
KDNA Lab ──→ 发现 registry 问题 → 触发修复
```

---

## 许可证

Apache 2.0
