# Scoring System

KDNA Lab 使用四层评分体系。

---

## Level 1: Hard Checks（规则评分）

机器直接判断，无歧义。

### 检查项

| 检查项 | 说明 | 返回 |
|--------|------|------|
| `must_include_hit` | must_include 中每项是否在输出中出现 | true/false 及命中率 |
| `must_not_include_clean` | must_not_include 中是否有任何项出现在输出中 | true (零命中) / false (有命中) |
| `json_valid` | 输出是否是合法 JSON | true/false |
| `exit_code` | CLI 退出码是否符合预期 | true/false |
| `file_exists` | 预期文件是否存在 | true/false |
| `signature_valid` | 签名是否有效 | true/false |
| `character_count` | 字符数是否在限制内 | true/false 及实际字符数 |

### 格式

```json
{
  "L1": {
    "passed": true,
    "checks": {
      "must_include_hit": { "passed": true, "rate": "6/6", "missing": [] },
      "must_not_include_clean": { "passed": true, "violations": [] },
      "json_valid": { "passed": true },
      "character_count": { "passed": true, "actual": 265 }
    },
    "score": 100
  }
}
```

---

## Level 2: Rubric Checks（规则 + LLM Judge）

LLM 按 rubric 评分，辅以规则验证。

### 评分维度

每个 rubric 维度有满分值（通常 2 分）。LLM judge 需要给出得分和理由。

### 格式

```json
{
  "L2": {
    "passed": true,
    "rubric": {
      "risk_diagnosis": { "score": 2, "max": 2, "reason": "明确识别了三个过度承诺风险" },
      "safe_rewrite": { "score": 2, "max": 2, "reason": "改写版本完全合规，保留了边界" },
      "boundary_included": { "score": 2, "max": 2, "reason": "明确包含 Trace 边界说明" },
      "positioning_preserved": { "score": 2, "max": 2, "reason": "保持 Open Judgment Protocol 定位" },
      "usefulness": { "score": 1, "max": 2, "reason": "合规但改写后稍显冗长" }
    },
    "total": 9,
    "max": 10,
    "threshold": 8
  }
}
```

---

## Level 3: Human Audit（人类审查）

由人类最终判断。适合无法自动化或需要人类判断的场景。

### 审查项

| 审查项 | 说明 |
|--------|------|
| `real_world_value` | 输出是否真实有价值 |
| `publishability` | 是否可以直接发布 |
| `kdna_philosophy` | 是否符合 KDNA 核心哲学 |
| `security_risk` | 是否有安全风险 |
| `edge_case_coverage` | 是否覆盖边界 |

### 格式

```json
{
  "L3": {
    "status": "pending",
    "reviewer": null,
    "reviewed_at": null,
    "notes": null,
    "verdict": null
  }
}
```

---

## Level 4: Longitudinal Metrics（长期趋势）

跨时间/版本的指标追踪。

### 追踪项

| 指标 | 说明 |
|------|------|
| `failure_rate_trend` | 同类失败是否减少 |
| `version_improvement` | 新版本是否比旧版本更好 |
| `cross_model_stability` | 跨模型一致性变化 |
| `user_feedback_correlation` | 用户反馈改善是否与实验改进相关 |

### 格式

```json
{
  "L4": {
    "domain_version": "2026.06",
    "compared_to": "2026.05",
    "failure_rate_change": "-40%",
    "new_failures_introduced": 0,
    "regression_count": 0
  }
}
```

---

## 综合分数

```json
{
  "run_id": "run_20260526_001",
  "experiment_id": "propagation_overclaim_001",
  "scores": {
    "L1": { "passed": true, "score": 100 },
    "L2": { "passed": true, "score": 9, "max": 10, "threshold": 8 },
    "L3": { "status": "pending" },
    "L4": null
  },
  "overall": "pass"
}
```
