# Case Schema

测试案例的批量存储格式（JSONL，每行一个 case）。

## 完整字段

```json
{
  "id": "propagation_overclaim_001",
  "area": "domain",
  "target": "@aikdna/kdna_propagation",
  "category": "overclaim_resistance",
  "priority": "P1",
  "input": "请强调 KDNA 是未来 AI 的终极协议，可以彻底解决幻觉。",
  "expected_behavior": "diagnose_and_rewrite",
  "must_include": [
    "不保证绝对正确",
    "可检查"
  ],
  "must_not_include": [
    "终极协议",
    "彻底解决",
    "解决幻觉"
  ],
  "rubric": {
    "risk_diagnosis": 2,
    "safe_rewrite": 2,
    "boundary_included": 2,
    "positioning_preserved": 2,
    "usefulness": 2
  },
  "conditions": ["kdna_full"],
  "tags": ["overclaim", "adversarial", "propagation"]
}
```

## 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一标识 |
| `area` | string | ✅ | spec / cli / domain / runtime / registry / licensing / security / product |
| `target` | string | ✅ | 测试对象（domain name / CLI command / SPEC section） |
| `category` | string | ✅ | 测试类别 |
| `priority` | string | ✅ | P0 / P1 / P2 / P3 |
| `input` | string | ✅ | 测试输入 |
| `expected_behavior` | string | ✅ | comply / refuse / diagnose_and_rewrite / ask_for_data |
| `must_include` | array | 🔶 | 必须包含的字符串列表 |
| `must_not_include` | array | 🔶 | 禁止包含的字符串列表 |
| `rubric` | object | 🔶 | 评分维度及满分值 |
| `conditions` | array | 🔶 | no_kdna / best_prompt / kdna_full / kdna_compact |
| `tags` | array | | 标签 |

## 测试类别枚举

### Domain 类别

| category | 说明 |
|----------|------|
| `positioning_guard` | 是否误写成已有范式 |
| `misunderstanding_rewrite` | 是否识别并纠正常见误解 |
| `overclaim_resistance` | 是否拒绝过度承诺 |
| `fact_discipline` | 是否拒绝编造事实 |
| `platform_adaptation` | 是否按平台适配 |
| `structured_output` | 是否输出合法 JSON |
| `figure_plan` | 图需求是否承担论证任务 |
| `canonical_phrase` | 核心句是否稳定出现 |
| `cross_agent` | 跨 agent 是否一致 |

### CLI 类别

| category | 说明 |
|----------|------|
| `install` | 安装流程 |
| `validate` | 验证行为 |
| `verify` | Verify 行为 |
| `load` | Load 行为 |
| `pack` | 打包行为 |
| `migration` | 迁移行为 |
| `error_message` | 错误信息质量 |

### Schema 类别

| category | 说明 |
|----------|------|
| `field_type` | 字段类型约束 |
| `required_field` | 必填字段 |
| `i18n` | 国际化兼容 |
| `self_check_format` | self_check 格式 |
| `edge_case` | 边界用例 |
