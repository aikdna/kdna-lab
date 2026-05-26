# KDNA Lab: Open vs. Internal Boundaries

KDNA Lab follows an **open-core strategy**.

> **The testing framework is open. Sensitive security and commercial validation suites are private.**

中文：**测试框架开放，敏感安全与商业验证套件私有。**

---

## Open: KDNA Lab Core

The following are open-sourced under Apache-2.0:

| Category | Content |
|----------|---------|
| **Schemas** | `case.schema.json`, `experiment.schema.json` — definitions of test formats |
| **Docs** | Architecture, case schema, experiment schema, scoring system, report format |
| **Runners** | Basic CLI runner, domain runner, cross-model runner |
| **Scorers** | Rule scorer (L1), LLM judge adapter interface (L2) |
| **Analyzers** | Failure classifier, patch proposer, regression analyzer |
| **Examples** | Public domain test cases (`kdna_propagation`, `cli`, `schema`) |
| **Fixtures** | Valid and invalid domain fixtures for schema testing |
| **Reports** | Report generator and sample public reports |

### Purpose

Open-sourcing the core proves that KDNA is not just a concept — it has a reproducible, extensible testing framework. Anyone can:

- Write new cases for public KDNA domains
- Contribute runners for new agents or models
- Verify CLI behavior across environments
- Reproduce published benchmarks

---

## Internal: KDNA Lab Pro

The following remain private and are not in this repository:

| Category | Content |
|----------|---------|
| **Security Red Team** | License bypass tests, registry attack payloads, watermark removal tests, signature replay attacks, domain exfiltration tests |
| **Marketplace** | Paid domain validation, Stripe integration tests, fraud detection logic, abuse patterns |
| **Licensing** | Encryption/decryption tests, entitlement verification, offline license behavior |
| **Enterprise** | Private domain tests, customer data evaluations, SSO integration tests, team permission tests |
| **Telemetry** | Real user feedback analysis, production failure clustering, proprietary benchmark datasets |
| **Competitive** | Internal roadmap evaluation, marketplace risk weights, commercial strategy tests |

### Why Private

1. **Security**: Publishing attack payloads is equivalent to distributing a penetration-testing manual to adversaries.
2. **Commercial**: Marketplace and licensing tests directly map to business logic and anti-cheat strategy.
3. **Privacy**: Real customer domains, user feedback, and team traces contain confidential information.
4. **Competition**: Internal quality weights and failure prioritization reveal strategic direction.

---

## Boundary Examples

| Topic | Open (Core) | Internal (Pro) |
|-------|-------------|----------------|
| Domain behavior test | How to test if `kdna_propagation` guards positioning | Tests of proprietary customer domains |
| CLI regression | `kdna validate` exit codes and error messages | `kdna install` against private registry with auth |
| Schema validation | JSON Schema for valid/invalid fields | Schema for encrypted commercial domain packages |
| Cross-agent portability | Whether banned terms survive across agents | Whether watermark survives model distillation |
| Failure analysis | Public failure types and fix suggestions | Customer-specific failure clusters |
| Report | Public benchmark report for `kdna_propagation` | Marketplace seller quality scorecards |

---

## Contributing

Contributions to KDNA Lab Core are welcome. See `CONTRIBUTING.md`.

If you have a security concern or need access to internal validation suites as an enterprise partner, contact the KDNA team directly.
