# arxpm

`arxpm` is the Arx project manager and workspace tool.

`arx` stays compiler-only. `arxpm` owns project manifests (`.arxproject.toml`),
workspace lifecycle, Pixi integration, and user-facing workflow commands.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `models.py`: typed manifest models.
- `manifest.py`: `.arxproject.toml` parsing and rendering.
- `_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `pixi.py`: Pixi adapter and `pixi.toml` handling.
- `project.py`: project workflows (`init`, `add`, `install`, `build`, `run`,
  `pack`, `publish`).
- `doctor.py`: health checks for environment and manifest.
- `cli.py`: Typer command layer.

## Commands (v0)

- `arxpm init`
- `arxpm install`
- `arxpm add <name> [--path PATH|--git URL]`
- `arxpm build`
- `arxpm compile`
- `arxpm run`
- `arxpm pack`
- `arxpm publish`
- `arxpm doctor`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
pytest
```

The `examples/` directory ships two sample projects:

- `examples/hello-arx/` — minimal single-file project.
- `examples/multi-module/` — multi-file project whose `main.x` imports and calls
  functions from sibling `.x` modules. See the
  [Multi-file Projects](docs/multi-file-projects.md) guide.

Integration tests that compile and execute both examples live in
`tests/test_examples_integration.py` and are gated on `arx` and `pixi` being on
`PATH`. Run them with:

```bash
pytest -m integration
```
