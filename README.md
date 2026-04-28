# arxpm

`arxpm` is the Arx project manager and workspace tool.

`arx` compiles `.x` files and resolves project-aware imports using
`build.src_dir`. `arxpm` owns `.arxproject.toml` rendering, project layout
inference and validation, default target selection, Python environment
provisioning (via `uv`), and user-facing workflow commands.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `models.py`: typed manifest models.
- `manifest.py`: `.arxproject.toml` parsing and rendering.
- `layout.py`: effective package/mode resolution and filesystem validation.
- `_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `environment.py`: backend-neutral environment protocol plus `venv`, `conda`,
  and `system` implementations that install packages via
  `uv pip install --python <interp>`.
- `credentials.py`: keyring-backed publish credential storage.
- `project.py`: project workflows (`init`, `add`, `install`, `build`, `run`,
  `pack`, `publish`).
- `healthcheck.py`: manifest, layout, environment, and toolchain checks.
- `cli.py`: Typer command layer.

## Commands (v0)

- `arxpm init`
- `arxpm config`
- `arxpm install`
- `arxpm add <name> [--path PATH|--git URL]`
- `arxpm build`
- `arxpm compile`
- `arxpm run`
- `arxpm pack`
- `arxpm publish`
- `arxpm healthcheck`
- `arxpm doctor`

## Development

```bash
mamba env create --file conda/dev.yaml
conda activate arxpm
poetry install --with dev
pytest
```

The `examples/` directory ships several sample projects:

- `examples/hello-arx/` — minimal app project at `src/hello_arx/`.
- `examples/multi-module/` — multi-file app project whose `main.x` imports and
  calls functions from sibling `.x` modules. See the
  [Multi-file Projects](docs/multi-file-projects.md) guide.
- `examples/local_lib/` + `examples/local-consumer/` — a library and a consumer
  that live side by side on disk so the consumer resolves imports against the
  library's installed `.x` files. See [Local Packages](docs/local-packages.md)
  for path dependencies and installed Arx package source links.

Integration tests that compile and execute the examples live in
`tests/test_examples_integration.py` and are gated on `arx` and `uv` being on
`PATH`. Run them with:

```bash
pytest -m integration
```
