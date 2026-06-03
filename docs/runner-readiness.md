# Runner Readiness

KDNA Lab should run from an isolated project environment. Do not install KDNA
Lab into the Homebrew/system Python with `sudo`, `--break-system-packages`, or
global pip writes.

## Recommended Local Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,runner,scorer]'
```

This installs the CLI entry points inside `.venv/bin/`:

```bash
.venv/bin/kdna-lab-run-domain --help
.venv/bin/kdna-lab-score --help
.venv/bin/kdna-lab-pipeline --help
```

## Smoke Checks

```bash
.venv/bin/pytest -q
.venv/bin/kdna-lab-run-domain examples/writing/cases.jsonl \
  --plan \
  --domain @aikdna/writing \
  --config /private/tmp/kdna-lab-smoke.yaml
.venv/bin/kdna-lab-pipeline run \
  --case-file examples/writing/cases.jsonl \
  --output-dir /private/tmp/kdna-lab-smoke
```

The plan command verifies case loading, domain loading, and prompt generation
without calling a model provider. The pipeline command verifies that structured
`benchmark-run-v1` artifacts can be discovered and scored.

## Why Not Global Install

macOS Homebrew Python is externally managed under PEP 668. The correct approach
is a local `.venv` for project work or `pipx` for a globally available isolated
application. For KDNA Lab development, `.venv` is preferred because the package
is installed editable and should reflect local source changes immediately.
