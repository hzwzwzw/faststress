# FastStress

Interactive TUI wrapper for `sglang.bench_serving` providing batch test case management, persistent presets, and automated SLO-based parameter optimization.

## Architecture

```
src/faststress/
├── app.py          # Textual app entry point
├── models.py       # Pydantic models (TestCase, TestGroup, Preset, BenchResult)
├── runner.py       # Subprocess wrapper for bench_serving, output parsing
├── optimizer.py    # Auto-optimization: grid/binary search for SLO targets
├── storage.py      # JSON/CSV persistence, import/export
├── widgets/        # Textual widgets
│   ├── case_list.py      # Test case list panel
│   ├── case_editor.py    # Test case editing form
│   ├── run_panel.py      # Execution status & output
│   └── optimizer_ui.py   # Auto-optimization interface
└── styles/
    └── app.tcss    # Textual CSS
```

## Key Commands

```bash
uv run faststress          # Launch TUI
uv run python -m faststress  # Alternative launch
```

## Development

```bash
uv sync                    # Install dependencies
uv run textual console     # Textual devtools
```

## Design Decisions

- **Textual** for TUI: rich widgets, async-native, keyboard-first
- **Pydantic** for data models: validation, serialization, schema
- Calls `python -m sglang.bench_serving` as subprocess (no library import needed)
- Results parsed from JSONL output files
- Presets and test cases stored as JSON in `~/.faststress/`
- CSV results auto-saved per run with timestamps

## bench_serving Integration

Supported backends: `sglang`, `sglang-oai`
Supported datasets: `random-ids`, `sharegpt`, `generated-shared-prefix`

The runner builds CLI args from TestCase model fields and spawns the process asynchronously, streaming stdout to the TUI run panel.
