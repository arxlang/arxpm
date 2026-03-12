# ArxPM

`arxpm` is the project and package manager for Arx workspaces.

## Scope

- `arx` is compiler-only.
- `arxpm` is the user-facing workflow tool.
- Pixi is the environment and toolchain backend.

Arx projects use `arxproj.toml` as their project manifest. Python packaging is
only for distributing `arxpm` itself.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `src/arxpm/models.py`: typed manifest models.
- `src/arxpm/manifest.py`: parse/render `arxproj.toml`.
- `src/arxpm/_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `src/arxpm/pixi.py`: Pixi detection and partial `pixi.toml` sync.
- `src/arxpm/project.py`: `init`, `add`, `install`, `build`, `run`, `publish`.
- `src/arxpm/doctor.py`: environment and manifest checks.
- `src/arxpm/cli.py`: Typer CLI layer.

## Quick CLI

```bash
arxpm init --name hello-arx
arxpm add http
arxpm install
arxpm build
arxpm run
arxpm publish
arxpm doctor
```

See [Getting Started](getting-started.md) for a full setup and
[Pixi Integration](pixi-integration.md) for ownership boundaries.
