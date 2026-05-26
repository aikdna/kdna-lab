# KDNA Propagation Domain — Test Protocol

This document defines the test protocol for `@aikdna/kdna_propagation`, the KDNA self-communication domain.

> **We use KDNA to communicate KDNA.**

This domain encodes the judgment required to produce technically credible, platform-adapted, visually guided public communication about KDNA as an open judgment protocol.

---

## Test Scope

| # | Category | Cases | Purpose |
|---|----------|-------|---------|
| 1 | Positioning Guard | `propagation_basic_intro_001` | Prevent KDNA from being mischaracterized as a prompt tool, knowledge base, or generic AI app |
| 2 | Misunderstanding Rewrite | `propagation_misclassification_rewrite_001` | Detect and correct misclassifications in input text |
| 3 | Overclaim Resistance | `propagation_overclaim_resistance_001` | Reject requests to use hype language ("ultimate", "solve all hallucinations") |
| 4 | Fact Discipline | `propagation_fact_discipline_001` | Refuse to fabricate statistics; request source data |
| 5 | Platform Adaptation | `propagation_x_post_001`, `propagation_platform_compression_001`, `propagation_wechat_visual_001` | Compress the same message for X, 小红书, 微信贴图, 公众号 |
| 6 | Structured Output | `propagation_json_output_001` | Output valid JSON with figure plans, boundary statements |
| 7 | Canonical Phrase | `propagation_required_phrase_001` | Enforce required phrases like "Trace 证明可检查性，不证明绝对正确" |
| 8 | Long-form Article | `propagation_long_article_001` | Produce 1200-1600 word articles with paper logic |

---

## Test Conditions

All domain behavior tests run under:

| Condition | Description |
|-----------|-------------|
| `kdna_full` | Domain fully loaded via `kdna load @aikdna/kdna_propagation` |

Future conditions (not yet implemented):

| Condition | Description |
|-----------|-------------|
| `no_kdna` | Raw model, no domain loaded — baseline comparison |
| `best_prompt` | Best-effort prompt without KDNA — comparison |
| `kdna_compact` | Compact profile loaded — for token-constrained environments |

---

## Hard Checks (L1)

For each case, the rule scorer verifies:

1. **Must Include**: All phrases in `must_include` appear in output (case-insensitive)
2. **Must Not Include**: No phrases in `must_not_include` appear unless negated (e.g., "KDNA is **not** a prompt library")
3. **JSON Valid**: If case is tagged `json`, output must contain valid JSON
4. **Character Count**: If case is tagged `x_post`, output must be ≤ 280 characters

---

## Rubric Checks (L2)

LLM judge scores each output on dimensions defined in the case `rubric`:

| Dimension | Typical Max | What it measures |
|-----------|-------------|------------------|
| `problem_defined` | 2 | Whether content starts with problem, not feature list |
| `paradigm_distinction` | 2 | Whether KDNA is distinguished from prompt/RAG/skill/workflow |
| `positioning_accurate` | 2 | Whether "open judgment protocol" positioning is preserved |
| `boundary_included` | 2 | Whether limitations and boundaries are stated |
| `mechanism_explained` | 2 | Whether KDNA's mechanism is explained, not just named |
| `figure_argumentative` | 2 | Whether figure plans serve argument, not decoration |
| `platform_differentiation` | 2 | Whether platform-specific versions are truly adapted |

Pass threshold: ≥ 80% of total rubric points.

---

## Running the Tests

### Generate run plans

```bash
python runners/run_domain_cases.py --plan \
  --domain @aikdna/kdna_propagation \
  examples/kdna_propagation/cases.jsonl
```

### Execute via API

```bash
python runners/run_domain_cases.py --execute \
  --domain @aikdna/kdna_propagation \
  examples/kdna_propagation/cases.jsonl
```

### Score outputs

```bash
python scorers/rule_scorer.py \
  examples/kdna_propagation/cases.jsonl \
  --json
```

### Full pipeline

```bash
# 1. Run
python runners/run_domain_cases.py --execute \
  --domain @aikdna/kdna_propagation \
  examples/kdna_propagation/cases.jsonl

# 2. Score
python scorers/rule_scorer.py \
  examples/kdna_propagation/cases.jsonl \
  --json > scores.json

# 3. Analyze failures
python analyzers/failure_classifier.py scores.json --json

# 4. Generate report
python reports/generate_report.py scores.json --type domain
```

---

## Expected Results

A healthy `@aikdna/kdna_propagation` domain should:

- Pass 100% of L1 hard checks on positioning guard cases
- Pass 100% of L1 hard checks on overclaim resistance cases
- Score ≥ 80% on L2 rubric for platform adaptation cases
- Never fabricate statistics on fact discipline cases
- Always include the canonical phrase on required phrase cases

---

## Evolution

This test protocol is versioned with the domain. When `@aikdna/kdna_propagation` evolves:

1. New eval cases are added to `cases.jsonl`
2. Runners are re-executed
3. Regression analyzer compares old vs. new scores
4. Patch proposals are generated for domain maintainers
5. Human review (L3) confirms real-world value
