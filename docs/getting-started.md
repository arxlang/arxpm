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
pip install -e '.[dev]'
```

## Verify Toolchain

```bash
python -m arxpm healthcheck --directory examples/hello-arx
```

The report should show:

- `.arxproject.toml` found
- manifest parses
- `uv` is available on PATH
- the configured compiler (`arx`) is on PATH
- the environment is configurable (defaults to a managed `.venv`)

## Run Examples

The `examples/` directory ships several projects:

- `examples/hello-arx/` — single-file project that prints a greeting.
- `examples/multi-module/` — multi-file project where `main.x` imports helpers
  from sibling modules (`math_utils.x`, `string_utils.x`). See
  [Multi-file Projects](multi-file-projects.md) for the layout.
- `examples/local_lib/` + `examples/local-consumer/` — path-dependency workflow
  where one Arx project depends on another. See
  [Local Packages](local-packages.md).

```bash
python -m arxpm install --directory examples/hello-arx
python -m arxpm build --directory examples/hello-arx
python -m arxpm run --directory examples/hello-arx

python -m arxpm install --directory examples/multi-module
python -m arxpm run --directory examples/multi-module
```

The first `install` creates `examples/hello-arx/.venv` via `uv venv`. The
multi-module run prints:

```
Hello, Arx!
5
```

## Publish Package

Set Twine credentials for your package index (PyPI example):

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<pypi-token>
python -m arxpm publish --directory examples/hello-arx
```

`publish` uses `python -m build` and `python -m twine` from the outer
interpreter running `arxpm`; it never installs build tooling into the project
environment.

## Local Quality Gates

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim docs.build
```
