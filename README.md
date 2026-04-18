# arxpm

`arxpm` is the Arx project manager and workspace tool.

`arx` stays compiler-only. `arxpm` owns project manifests (`.arxproject.toml`),
workspace lifecycle, Python environment provisioning (via `uv`), and user-facing
workflow commands.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `models.py`: typed manifest models.
- `manifest.py`: `.arxproject.toml` parsing and rendering.
- `_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `environment.py`: backend-neutral environment protocol plus managed-venv,
  existing-venv, and conda implementations that install packages via
  `uv pip install --python <interp>`.
- `project.py`: project workflows (`init`, `add`, `install`, `build`, `run`,
  `pack`, `publish`).
- `healthcheck.py`: health checks for environment and manifest.
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
- `arxpm healthcheck`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

The `examples/` directory ships several sample projects:

- `examples/hello-arx/` — minimal single-file project.
- `examples/multi-module/` — multi-file project whose `main.x` imports and calls
  functions from sibling `.x` modules. See the
  [Multi-file Projects](docs/multi-file-projects.md) guide.
- `examples/local_lib/` + `examples/local-consumer/` — a library and a consumer
  that live side by side on disk so the consumer resolves imports against the
  library's `.x` files. See [Local Packages](docs/local-packages.md) for the
  supported layout and the current boundary around installed libraries.

Integration tests that compile and execute the examples live in
`tests/test_examples_integration.py` and are gated on `arx` and `uv` being on
`PATH`. Run them with:

```bash
pytest -m integration
```
