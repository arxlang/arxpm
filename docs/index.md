# ArxPM

`arxpm` is the project and package manager for Arx workspaces.

## Scope

- `arx` is compiler-only.
- `arxpm` is the user-facing workflow tool.
- Python environments are backend-neutral: a project can use a project-local
  venv (default), an existing venv, or a conda environment. `uv` is used to
  install packages in all cases.

Arx projects use `.arxproject.toml` as their project manifest. Python packaging
is only for distributing `arxpm` itself.

## Compatibility

- Python 3.10+ is supported.
- On Python 3.10, `arxpm` uses `tomli` as a compatibility fallback for
  `tomllib`.

## Architecture

- `src/arxpm/models.py`: typed manifest models.
- `src/arxpm/manifest.py`: parse/render `.arxproject.toml`.
- `src/arxpm/_toml.py`: TOML parser compatibility shim (`tomllib`/`tomli`).
- `src/arxpm/environment.py`: environment runtime abstraction and the
  managed-venv, existing-venv, and conda implementations.
- `src/arxpm/project.py`: `init`, `add`, `install`, `build`, `run`, `pack`,
  `publish`.
- `src/arxpm/healthcheck.py`: environment and manifest checks.
- `src/arxpm/cli.py`: Typer CLI layer.

## Quick CLI

```bash
arxpm init --name hello-arx
arxpm add http
arxpm install
arxpm build
arxpm compile
arxpm run
arxpm pack
arxpm publish
arxpm healthcheck
```

See [Getting Started](getting-started.md) for a full setup and
[Environments](environments.md) for the supported environment strategies.
