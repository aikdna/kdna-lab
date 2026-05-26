# Fixture Index

| Fixture | Violation | Expected Behavior |
|---------|-----------|-------------------|
| `valid_minimal_domain` | None | `kdna validate` passes |
| `invalid_string_judgment_role` | `judgment_role` is string instead of object | `kdna validate` fails with type error |
| `invalid_array_risk_model` | `risk_model` is array instead of object | `kdna validate` fails with type error |
| `invalid_string_action_template` | `action_template` is string instead of array | `kdna validate` fails with type error |
| `invalid_missing_boundary_fields` | `boundaries` items missing `rule` and `why` | `kdna validate` fails with required field error |
| `invalid_seven_json_files` | 7 KDNA JSON files (Core+Patterns+Scenarios+Cases+Reasoning+Evolution+Extra) | `kdna validate` fails: more than 6 files |
| `legacy_unscoped_domain` | `kdna.json` name is `fixture_legacy` (no @scope) | `kdna install` from local dir warns about scope |
