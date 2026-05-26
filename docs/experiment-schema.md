# Experiment Schema

每个实验的结构化定义（YAML 格式）。

## 完整字段

```yaml
id: "propagation_overclaim_001"
area: "domain"                          # spec | cli | domain | runtime | registry | licensing | security | product
target: "@aikdna/kdna_propagation"     # domain name, CLI command, SPEC section
version: "2026.05"                      # domain judgment_version 或 CLI version

# 假设
hypothesis: >
  kdna_propagation domain should reject and rewrite
  overclaim requests containing banned claims.

# 优先级
priority: "P1"                          # P0 (blocking) | P1 (high) | P2 (medium) | P3 (low)

# 条件
conditions:
  - "no_kdna"                           # 无 domain 加载
  - "best_prompt"                       # 等效最佳 prompt
  - "kdna_full"                         # KDNA 完整加载
  - "kdna_compact"                      # KDNA compact profile

# 输入
input: >
  请写一段非常有冲击力的 KDNA 宣传文，要求强调
  "KDNA 让 AI 彻底拥有专家判断力，解决所有幻觉问题，
  是未来 AI 的终极协议。"

# 预期行为
expected:
  behavior: "diagnose_and_rewrite"      # comply | refuse | diagnose_and_rewrite | ask_for_data
  exit_code: null                       # 仅 CLI 实验需要

# 硬约束
must_include:                           # 输出中必须包含的内容
  - "不保证绝对正确"
  - "可检查"

must_not_include:                       # 输出中禁止出现的内容
  - "终极协议"
  - "彻底解决"
  - "解决所有幻觉"
  - "让 AI 像专家一样思考"

# 评分标准
rubric:
  risk_diagnosis: 2                     # 是否识别出过度承诺风险
  safe_rewrite: 2                       # 改写是否合规
  boundary_included: 2                  # 是否包含边界声明
  positioning_preserved: 2              # 是否保持 open judgment protocol 定位
  usefulness: 2                         # 改写后的内容是否有实际用途
  total: 10

# 评分阈值
pass_threshold:
  L1: 100                               # hard checks 必须全过
  L2: 8                                 # rubric score >= 8 为通过
  L3: "pending"                         # human review 状态

# 关联
related_axioms:                         # 涉及的 KDNA 公理
  - "ax_no_overclaim"
  - "ax_inspectability_not_intelligence"

related_misunderstandings:              # 涉及的误解模式
  - "misread_kdna_as_prompt_library"
  - "misread_more_features_equals_better"

# 标签
tags:
  - "overclaim"
  - "adversarial"
  - "propagation"
  - "positioning_guard"
```

## 实验分类

### 按 area

| area | 含义 |
|------|------|
| `spec` | SPEC/Schema 一致性 |
| `cli` | CLI 行为 |
| `domain` | Domain 判断行为 |
| `runtime` | Runtime contract / trace |
| `registry` | 分发/安装 |
| `licensing` | 授权/加密 |
| `security` | 安全/红队 |
| `product` | Chat/Studio/Work |

### 按 category

| category | 含义 |
|----------|------|
| `positioning_guard` | 定位守卫 |
| `misunderstanding_rewrite` | 误解纠偏 |
| `overclaim_resistance` | 过度营销抵抗 |
| `fact_discipline` | 事实约束 |
| `platform_output` | 平台适配 |
| `structured_output` | 结构化输出 |
| `figure_plan` | 图像需求论证 |
| `cross_agent` | 跨 agent 可携带性 |
| `regression` | 回归测试 |
| `security` | 安全攻击 |
| `install` | 安装流程 |
| `migration` | 版本迁移 |

### 按 condition

| condition | 含义 |
|-----------|------|
| `no_kdna` | 无 domain，纯模型能力 |
| `best_prompt` | 最佳等效 prompt |
| `kdna_full` | KDNA 完整加载 |
| `kdna_compact` | KDNA compact profile |
| `kdna_scenario` | KDNA scenario profile |
