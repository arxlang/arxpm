# arxpm

`arxpm` is the Arx project manager and workspace tool.

`arx` stays compiler-only. `arxpm` owns project manifests (`arxproj.toml`),
workspace lifecycle, Pixi integration, and user-facing workflow commands.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `models.py`: typed manifest models.
- `manifest.py`: `arxproj.toml` parsing and rendering.
- `_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `pixi.py`: Pixi adapter and `pixi.toml` handling.
- `project.py`: project workflows (`init`, `add`, `install`, `build`, `run`,
  `publish`).
- `doctor.py`: health checks for environment and manifest.
- `cli.py`: Typer command layer.

## Commands (v0)

- `arxpm init`
- `arxpm install`
- `arxpm add <name> [--path PATH|--git URL]`
- `arxpm build`
- `arxpm run`
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

Use the `examples/` directory for sample manifest files.
