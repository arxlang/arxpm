# Getting Started

This guide sets up `arxpm` for local development and smoke testing.

## Prerequisites

- Python 3.10+
- `uv` (install with `pip install uv` or from the uv binary release)
- Conda or Mamba (optional; used for the repo's dev conda env)

## Setup

```bash
git clone https://github.com/arxlang/arxpm.git
cd arxpm
mamba env create --file conda/dev.yaml
conda activate arxpm
poetry install --with dev
```

## Verify Toolchain

```bash
python -m arxpm install --directory examples/hello-arx
python -m arxpm healthcheck --directory examples/hello-arx
```

The report should show:

- `.arxproject.toml` found
- manifest parses
- package name is valid
- source root and package root exist
- `__init__.x` exists
- `main.x` matches the resolved mode
- `uv` is available on PATH
- the Arx compiler and installed-package discovery are available from the
  configured environment
- the environment is reachable (defaults to a project `.venv`)

## Run Examples

The `examples/` directory ships several projects:

- `examples/hello-arx/` — app project rooted at `src/hello_arx/`.
- `examples/multi-module/` — multi-file app project rooted at
  `src/multi_module/`.
- `examples/local_lib/` + `examples/local-consumer/` — path-dependency workflow
  with a library package and an app package.
