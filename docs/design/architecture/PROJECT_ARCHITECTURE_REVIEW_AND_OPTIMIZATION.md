# Lumina Architecture Review and Optimization

## 1. Current Architecture Summary

Lumina follows a clear processing backbone:

1. CLI entry (`src/lumina/cli.py`) receives user command and builds runtime config.
2. Harness orchestrator (`src/lumina/harness.py`) controls end-to-end workflow.
3. Planner (`src/lumina/planner.py`) scans and plans files.
4. Executor (`src/lumina/executor.py`) generates note content through LLM providers.
5. Validator (`src/lumina/validator.py`) scores quality and feeds repair loops.
6. Optional subsystems handle cache/history/vector indexing and web UI.

This is a solid pipeline architecture with extensibility points (plugins, tools, web API).

## 2. Main Design Strengths

- Strong orchestrator pattern in Harness.
- Clear separation of planning/execution/validation concerns.
- Good operational modules: cache, history, vector store, incremental processing.
- CLI and web interface expose the same core capabilities.

## 3. Key Risks Found

- Domain layering drift: some modules under `core/` and top-level modules overlap responsibilities.
- Architecture and operations docs are spread across many markdown files with duplicated status blocks.
- Test system was fragmented: pytest tests in `tests/`, script checks in repository root.
- Root-level script checks were hard to govern and easy to forget in CI/local routines.

## 4. Optimization Implemented (This Migration)

### 4.1 Unified test topology

- Moved root-level script checks into `tests/manual/`.
- Renamed manual scripts to avoid pytest auto collection:
  - `tests/manual/validate_lumina_v2.py`
  - `tests/manual/validate_optimizations.py`
  - `tests/manual/validate_file_edit_tool.py`
  - `tests/manual/validate_flask_json.py`
  - `tests/manual/verify_imports.py`
- Added `tests/manual/run_all_manual_checks.py` as one-command runner.

### 4.2 Layered pytest structure

- Unit tests moved into `tests/unit/`.
- Integration tests moved into `tests/integration/`.
- Added `tests/README.md` with conventions and run commands.

## 5. Recommended Next Architecture Steps

1. Introduce service boundaries around `Harness` side-effects.
   - Extract storage adapters (history/cache/vector) behind interfaces.
2. Normalize package layering.
   - Decide single owner for incremental processing APIs (either `core/` or top-level orchestrator helpers).
3. Add a focused `tests/fixtures/` package.
   - Share file builders, fake notes, and config fixtures.
4. Add CI matrix by test tier.
   - unit on every push, integration on PR, manual scripts on release/nightly.
5. Create an architecture index doc.
   - one page linking `planner/executor/validator` contracts and extension points.

## 6. Test Governance Policy (Suggested)

- `tests/unit/`: no network, no external LLM dependency.
- `tests/integration/`: may use temporary filesystem and in-memory adapters.
- `tests/manual/`: script diagnostics for local pre-release checks only.
- No `test_*.py` files at repository root.
