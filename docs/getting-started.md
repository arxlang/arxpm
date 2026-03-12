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
python -m arxpm doctor --directory examples
```

The report should show:

- pixi available
- `arxproj.toml` found
- `pixi.toml` found
- `python`, `pip`, and `clang` declared in `pixi.toml`

## Run Example

```bash
python -m arxpm install --directory examples
python -m arxpm build --directory examples
python -m arxpm run --directory examples
```

## Publish Package

Set Twine credentials for your package index (PyPI example):

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<pypi-token>
python -m arxpm publish --directory examples
```

## Local Quality Gates

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim docs.build
```
