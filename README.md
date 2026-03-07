# arxpm

`arxpm` is the Arx project manager and workspace tool.

`arx` stays compiler-only. `arxpm` owns project manifests (`arxproj.toml`),
workspace lifecycle, Pixi integration, and user-facing workflow commands.

## Architecture

- `models.py`: typed manifest models.
- `manifest.py`: `arxproj.toml` parsing and rendering.
- `pixi.py`: Pixi adapter and `pixi.toml` handling.
- `project.py`: project workflows (`init`, `add`, `install`, `build`, `run`).
- `doctor.py`: health checks for environment and manifest.
- `cli.py`: Typer command layer.

## Commands (v0)

- `arxpm init`
- `arxpm install`
- `arxpm add <name> [--path PATH|--git URL]`
- `arxpm build`
- `arxpm run`
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
