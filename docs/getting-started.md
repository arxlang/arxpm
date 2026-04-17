# Getting Started

This guide sets up `arxpm` for local development and smoke testing.

## Prerequisites

- Python 3.10+
- Conda or Mamba
- Poetry

## Setup

```bash
git clone https://github.com/arxlang/arxpm.git
cd arxpm
mamba env create --file conda/dev.yaml
conda activate arxpm
poetry config virtualenvs.create false
poetry install --with dev
```

## Verify Toolchain

```bash
python -m arxpm doctor --directory examples/hello-arx
```

The report should show:

- pixi available
- `.arxproject.toml` found
- `pixi.toml` found
- `python`, `pip`, and `clang` declared in `pixi.toml`

## Run Examples

The `examples/` directory ships two projects:

- `examples/hello-arx/` — single-file project that prints a greeting.
- `examples/multi-module/` — multi-file project where `main.x` imports helpers
  from sibling modules (`math_utils.x`, `string_utils.x`). See
  [Multi-file Projects](multi-file-projects.md) for the layout.

```bash
python -m arxpm install --directory examples/hello-arx
python -m arxpm build --directory examples/hello-arx
python -m arxpm run --directory examples/hello-arx

python -m arxpm install --directory examples/multi-module
python -m arxpm run --directory examples/multi-module
```

The multi-module run prints:

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

## Local Quality Gates

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim docs.build
```
