# ArxPM

`arxpm` is the project and package manager for Arx workspaces.

## Scope

- `arx` is compiler-only.
- `arxpm` resolves project layout, validates package roots, and chooses default
  build targets.
- Python environments are backend-neutral: a project can use a project-local
  venv (default), a conda environment, or the current system interpreter. `uv`
  is used to install packages in all cases.

## Architecture

- `src/arxpm/models.py`: typed manifest models.
- `src/arxpm/manifest.py`: parse/render `.arxproject.toml`.
- `src/arxpm/layout.py`: resolve effective `src_dir`, `package`, and `mode`.
- `src/arxpm/environment.py`: environment runtime abstraction and the `venv`,
  `conda`, and `system` implementations.
- `src/arxpm/project.py`: `init`, `add`, `install`, `build`, `run`, `pack`,
  `publish`.
- `src/arxpm/healthcheck.py`: manifest, layout, environment, and toolchain
  checks.
- `src/arxpm/cli.py`: Typer CLI layer.

## Quick CLI

```bash
arxpm init --name hello-arx
arxpm add http
arxpm install
arxpm build
arxpm run
arxpm doctor
```
