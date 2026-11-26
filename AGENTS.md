# AI Contributor Guide: arxpm

This file is the shared operating manual for contributors working in `arxpm`.
Keep implementation style, review standards, and delivery quality consistent
across agents and humans.

## Project Snapshot

- Package: `arxpm`, a project and package manager for Arx workspaces.
- Python: `>=3.10,<4`; Python 3.10 uses `tomli`, while newer Python uses
  `tomllib`.
- CLI: Typer app exposed as `arxpm = arxpm.cli:app`.
- Key dependencies: `typer`, `arxlang`, `tomli`, `twine`, `build`, `uv`, and
  `keyring`; Poetry Core builds the package.
- Docs stack: MkDocs, Material, mkdocstrings, and the Jupyter notebook plugins
  configured in `pyproject.toml`.

## Core Objectives

1. Preserve manifest, layout, environment, CLI, packaging, and publish behavior
   unless the request explicitly changes it.
2. Keep typed models, filesystem validation, subprocess boundaries, tests, and
   docs aligned.
3. Keep quality gates green: unit coverage, smoke tests, pre-commit, Ruff,
   strict mypy, and docs build.
4. Make minimal, targeted edits with clear intent.

## Codex Authoring Rule

- Never use heredocs inside YAML files. Use plain YAML-safe commands or move
  script logic into a repository file.
- Do not modify remote repositories, publish packages, open PRs, or merge
  changes without explicit authorization.

## Repository Layout

- `src/arxpm/models.py`: typed manifest/environment/dependency models and
  validation.
- `src/arxpm/manifest.py`: `.arxproject.toml` loading, rendering, and
  dependency-group validation.
- `src/arxpm/layout.py`: effective source/build layout and package-name
  validation.
- `src/arxpm/_toml.py`: `tomllib`/`tomli` compatibility import.
- `src/arxpm/environment.py`: backend-neutral environment protocol for `venv`,
  `conda`, and `system` runtimes with `uv pip` installation.
- `src/arxpm/credentials.py`: keyring-backed publish credentials and
  repository/environment fallbacks.
- `src/arxpm/project.py`: init, install, build, run, pack, and publish
  workflows.
- `src/arxpm/healthcheck.py`: manifest, layout, environment, and compiler health
  checks.
- `src/arxpm/external.py`: external subprocess execution and structured results.
- `src/arxpm/errors.py`: typed public exception hierarchy.
- `src/arxpm/cli.py`: Typer command and option layer.
- `src/arxpm/__main__.py`: `python -m arxpm` entry point.
- `tests/`: unit and integration tests, including example-project smoke
  coverage.
- `examples/`: app and library sample projects with `.x` source modules and
  `.arxproject.toml` manifests.
- `docs/`: MkDocs source for commands, manifests, environments, and workflows.
- `.makim.yaml`: canonical local tasks.
- `.github/workflows/`: main, docs, and release workflows.

## Code Style & Standards

- Python 4-space indentation, strict type annotations, and Ruff line length 79.
- Ruff target Python 3.11 with `E`, `F`, `I`, `UP`, and `B` rules.
- mypy is strict, uses `mypy_path = "src"`, checks `src`, and targets Python
  3.11.
- Pre-commit runs whitespace and EOF fixes, JSON/TOML/XML checks, debug and
  private-key checks, Prettier, Ruff format/check, Douki sync, strict mypy,
  shellcheck, bandit, and mccabe.
- Markdown uses `.prettierrc.yaml`: the `remark` parser, `proseWrap: always`,
  and print width 80.
- Python source docstrings use Douki YAML fields such as `title`, `summary`,
  `parameters`, `attributes`, and `returns`. Preserve existing contracts and
  update them only when changed behavior makes them inaccurate.
- `.x` files in `examples/` begin with a Douki module docstring at line 1,
  column 1. Preserve their existing syntax and two-space indentation.
- Use guard clauses and explicit error types. Keep subprocess, credential,
  filesystem, and manifest failures at their owning boundaries.
- `atpublic`, `typeguard`, and `plum-dispatch` are not used in `arxpm`; do not
  add those conventions merely to match another repository.

## Tooling & Commands

Create the development environment:

```bash
mamba env create --file conda/dev.yaml
conda activate arxpm
poetry install --with dev
```

Canonical local checks:

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim tests.ci
makim docs.build
makim release.dry
```

`tests.unit` runs pytest with `--cov=arxpm`, a 90% coverage requirement, and
term-missing reporting. `tests.smoke` copies every example project to a
temporary directory and requires both `uv` and `arx` to healthcheck, install,
build, and run app examples. `tests.linter` installs the pre-commit hook and
runs it across all files.

## CI, Testing & Docs Contracts

- Main CI pushes and pull requests to `main`.
- The test matrix uses Ubuntu with Python 3.10, 3.11, 3.12, 3.13, and 3.14.
- Ubuntu/Python 3.10 runs the linter stack.
- Tests run `makim tests.unit`; smoke tests run `makim tests.smoke`.
- The docs workflow builds `mkdocs.yaml` on push, pull request, and manual
  dispatch.
- The release workflow performs `makim release.dry` on normal events and
  `makim release.ci` only for manual dispatch.
- Prefer a focused existing pytest test/node first. Add integration smoke
  coverage only for behavior exercised through real example projects.
- `90%` coverage is a minimum, not evidence by itself.
- Update the smallest relevant guide in `docs/` or `README.md` only when a
  public CLI, manifest, environment, or workflow contract changes.

## Reusable Agent Skills

Task workflows and detailed coding guidance live in
`.agents/skills/<skill-name>/SKILL.md`. Select skills for API design, issue
work, implementation planning, CI debugging, reviews, Python style, testing,
Douki docstrings, release checks, PR operations, or issue triage.

Apply `minimal-change` and `implementation-planning` to implementation and
planning work. These skills supplement, rather than override, this contributor
guide.
