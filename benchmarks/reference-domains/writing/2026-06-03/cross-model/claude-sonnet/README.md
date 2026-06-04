# Claude Sonnet — Cross-Model Run (FAILED)

## Status: Model Unavailable on API Tier

All 90 API calls returned provider errors. Claude Sonnet (`anthropic/claude-sonnet-4-20250514`) is not available on the current OpenRouter API tier. The raw artifact contains 90 entries with `error: provider_call_failed_or_timed_out`.

This run does not count as a successful cross-model benchmark and must not be used in cross-model stability claims.

## Artifacts

- `raw/run_*_benchmark-run-v1.raw.json` — 90 entries, all with provider errors
- `raw/*_benchmark-run-v1.scored.json` — L2 skipped all 90 (status: not_run)

## Next Steps

Retry with a supported API tier or use a different provider that has Claude Sonnet access.
