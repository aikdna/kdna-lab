# Contributing to KDNA Lab

KDNA Lab is the experimental infrastructure for the KDNA ecosystem. Contributions in the form of test cases, runners, scorers, fixtures, or documentation are welcome.

---

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Project Structure

```
kdna_lab/                  # Python package (core logic)
  __init__.py              # Public API exports
  cases.py                 # JSONL case loading
  checks.py                # L1 hard checks (must_include, etc.)
  config.py                # Config loading
  outputs.py               # Output discovery/parsing
  paths.py                 # Path resolution
  runner.py                # ExperimentRunner base class
  domain_runner.py         # Domain behavior runner
  cli_runner.py            # CLI regression runner
  rule_scorer.py           # L1 rule scorer
  report.py                # Multi-format report generator
  evidence_store.py        # Experiment data archival
  registry_check.py        # Registry integrity validator
  schema_check.py          # Domain schema validator
  spec_check.py            # SPEC consistency + App Contract
  portability_check.py     # Cross-agent portability tester
  scoring_pipeline.py      # L1→L2→L3 unified pipeline
  badge_check.py           # Quality badge evidence gate
  evolution_tracker.py     # Domain evolution + Human Lock
examples/                  # Test case collections (JSONL)
  cli/cases.jsonl          # CLI regression cases
  kdna_propagation/        # Domain behavior cases
  schema/cases.jsonl       # Schema validation cases
  writing/cases.jsonl      # Writing domain cases
fixtures/                  # Test domain packages
tests/                     # Unit tests
```

## CLI Tools

| Command | Purpose |
|---------|---------|
| `kdna-lab-run-cli` | Run CLI regression tests |
| `kdna-lab-run-domain` | Run domain behavior tests |
| `kdna-lab-score` | Score outputs with L1 checks |
| `kdna-lab-report` | Generate reports |
| `kdna-lab-registry` | Validate registry integrity |
| `kdna-lab-schema` | Validate domains against schemas |
| `kdna-lab-spec` | Check SPEC + App Contract |
| `kdna-lab-evidence` | Query evidence store |
| `kdna-lab-portability` | Cross-agent portability tests |
| `kdna-lab-pipeline` | L1→L2→L3 scoring pipeline |
| `kdna-lab-badge` | Quality badge computation |
| `kdna-lab-evolution` | Domain evolution tracking |

---

## What KDNA Lab Needs

| Area | Good First Contribution |
|------|------------------------|
| **Cases** | Add eval cases for public KDNA domains (`@aikdna/writing`, `@aikdna/code_review`, etc.) |
| **Agent Profiles** | Add new agent profiles in `portability_check.py` (Cursor, Copilot, etc.) |
| **Runners** | Add runner support for new experiment types |
| **Scorers** | Improve rule scorer accuracy, add new L1 check types |
| **Fixtures** | Add valid/invalid domain fixtures for schema testing |
| **Reports** | New report formats (e.g., paper LaTeX, GitHub issue body) |
| **Docs** | Improve architecture docs, add test protocols for domains |

---

## Adding New Cases

Cases are stored as JSONL (one JSON object per line) in `examples/<area>/cases.jsonl`.

Minimal valid case:

```json
{
  "id": "domain_myfeature_001",
  "area": "domain",
  "target": "@aikdna/my_domain",
  "category": "positioning_guard",
  "priority": "P1",
  "input": "Prompt or command here.",
  "expected_behavior": "comply",
  "must_include": ["required phrase"],
  "must_not_include": ["banned phrase"],
  "conditions": ["kdna_full"],
  "tags": ["my_domain", "baseline"]
}
```

Place new cases in `examples/<domain>/cases.jsonl`.

---

## Adding Agent Profiles

Add to `AGENT_PROFILES` in `kdna_lab/portability_check.py`:

```python
"new_agent": {
    "id": "new_agent",
    "name": "New Agent Name",
    "description": "What this agent does",
    "system_prompt": "The agent's default system instructions...",
    "instruction_style": "concise",  # or "verbose"
    "default_model": "gpt-4o",
    "provider": "openai",
},
```

---

## Adding Fixtures

Create a directory under `fixtures/<name>/` with:

```
fixtures/my_invalid_domain/
  kdna.json
  KDNA_Core.json
  KDNA_Patterns.json
```

Add an entry to `fixtures/README.md`.

---

## Running Tests

```bash
# Unit tests
pytest tests/ -v

# CLI regression (requires kdna CLI installed)
kdna-lab-run-cli --run

# Schema validation (requires OPEN_SOURCE/kdna/schema/)
kdna-lab-schema --fixtures

# SPEC check
kdna-lab-spec --all
```

---

## Security

**Do not contribute:**
- Security attack payloads or red-team cases
- Tests for paid/encrypted domains
- Real customer data or private domain content
- Marketplace fraud or license bypass tests

These belong in `kdna-lab-internal`.

---

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.
