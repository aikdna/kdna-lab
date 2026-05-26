# Contributing to KDNA Lab

Thank you for contributing to KDNA Lab. This document covers what you need to know.

---

## What KDNA Lab Needs

| Area | Good First Contribution |
|------|------------------------|
| **Cases** | Add eval cases for public KDNA domains (e.g., `@aikdna/writing`) |
| **Runners** | Add runner support for new agents (Cursor, Copilot, etc.) |
| **Scorers** | Improve rule scorer accuracy or add new L1 check types |
| **Fixtures** | Add valid/invalid domain fixtures for schema testing |
| **Docs** | Clarify schema docs, add test protocol for your domain |
| **Reports** | New report formats (e.g., GitHub issue body, paper LaTeX) |

---

## Contribution Workflow

1. **Fork** the repository
2. **Branch** from `main`: `git checkout -b add-x-post-cases`
3. **Write** your change
4. **Test** locally:
   ```bash
   python -m py_compile scorers/*.py runners/*.py analyzers/*.py
   python scorers/rule_scorer.py examples/<your-domain>/cases.jsonl --json
   ```
5. **Commit** with a clear message:
   ```
   Add X post thread cases for kdna_propagation

   - Adds 3 thread-format cases (280 char limit)
   - Tests hook + problem + boundary structure
   ```
6. **Open a Pull Request** with:
   - What you changed
   - Why it matters
   - Test results (pass/fail counts)

---

## Code Style

- Python: follow PEP 8
- JSON/JSONL: use 2-space indent, UTF-8, no trailing commas
- YAML: 2-space indent
- Case IDs: `{area}_{category}_{sequence:03d}`

---

## Adding New Cases

Cases are stored as JSONL (one JSON object per line).

Minimal valid case:

```json
{
  "id": "domain_myfeature_guard_001",
  "area": "domain",
  "target": "@aikdna/my_domain",
  "category": "my_category",
  "priority": "P1",
  "input": "Prompt text here.",
  "expected_behavior": "comply",
  "must_include": ["required phrase"],
  "must_not_include": ["banned phrase"],
  "conditions": ["kdna_full"],
  "tags": ["my_domain", "baseline"]
}
```

Place new cases in `examples/<domain>/cases.jsonl`.

---

## Adding New Fixtures

Fixtures are test domain packages used for CLI/schema tests.

Create a directory under `fixtures/<name>/` with:

```
fixtures/my_invalid_domain/
  kdna.json
  KDNA_Core.json
  KDNA_Patterns.json
```

Add an entry to `fixtures/README.md` describing the violation and expected behavior.

---

## Security and Sensitive Content

**Do not contribute:**

- Security attack payloads or red-team cases
- Tests for paid/encrypted domains
- Real customer data or private domain content
- Marketplace fraud or license bypass tests

These belong in the internal KDNA Lab Pro repository. If you have a security concern, contact the maintainers directly.

---

## Questions?

- Open a GitHub Discussion for questions
- Open a GitHub Issue for bugs
- Tag `@aikdna/kdna-lab-maintainers` for review requests

---

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.
