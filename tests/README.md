# Test Topology

This project uses a layered test layout so test ownership is explicit.

## Layout

- `tests/unit/`: fast, isolated unit tests for modules and pure logic.
- `tests/integration/`: cross-module behavior tests.
- `tests/manual/`: script-style validation checks (not collected by pytest).

## Run Commands

Run all pytest tests:

```bash
python -m pytest tests/ -v
```

Run unit tests only:

```bash
python -m pytest tests/unit -v
```

Run integration tests only:

```bash
python -m pytest tests/integration -v
```

Run manual validation suite:

```bash
python tests/manual/run_all_manual_checks.py
```

## Rules

- New pytest tests must go to `tests/unit/` or `tests/integration/`.
- Script validation checks must go to `tests/manual/` and should avoid the `test_*.py` naming pattern.
- Do not add test scripts to the repository root.
