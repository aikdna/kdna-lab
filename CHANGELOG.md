# Changelog

## 2026-05-30
- L2 Judge: fixed reasoning model output (content vs .reasoning fallback)
- Trace checker: 0%→72% pass rate, supports judgment-report and JSONL formats
- Provider adapter: handles reasoning models transparently
- Version compatibility: updated expectations for relaxed schema limits
- max_tokens: bumped to 4000 for L2 Judge

## 2026-05-29
- Initial release: 30 experiments, 166 test cases, 14 CLI entry points
- L1/L2/L3 scoring pipeline, schema/registry/spec validation
- Cross-model comparison, 3-condition (no_kdna/best_prompt/kdna_full) framework
- Portability framework, runtime pipeline, trace completeness checker
