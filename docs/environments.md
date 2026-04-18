# Environments

`arxpm` does not bundle its own Python environment. Every project declares how
its Python environment should be provided, and `arxpm` uses
[`uv`](https://github.com/astral-sh/uv) to install packages into the interpreter
you point it at.

Three strategies are supported out of the box, each declared in
`.arxproject.toml` via the `[environment]` table.

## Strategy 1 — Managed venv (default)

`arxpm` creates and maintains a project-local virtual environment using
`uv venv`. This is the default when `.arxproject.toml` has no `[environment]`
section.

```toml
[environment]
kind = "managed-venv"
path = ".venv"   # optional; defaults to ".venv"
```

Behavior:

- `arxpm install` runs `uv venv <path>` if the venv does not yet exist, then
  `uv pip install --python <venv>/bin/python ...` for your dependencies.
- `arxpm run` and `arxpm build` do not touch the venv; they invoke the `arx`
  compiler directly from the outer PATH.

Omit the whole `[environment]` section for the simplest projects — the defaults
match what you'd write by hand.

## Strategy 2 — Existing venv

Reuse a virtual environment that you manage yourself (for example, a team-wide
`.venv` or an IDE-managed interpreter):

```toml
[environment]
kind = "existing-venv"
path = ".venv"   # required; relative to the project root or absolute
```

Behavior:

- `arxpm install` validates that `<path>` is a directory with a usable
  `bin/python` (Windows: `Scripts/python.exe`) and installs packages via
  `uv pip install --python <interp>`. It never creates the venv for you.

## Strategy 3 — Conda environment

Point `arxpm` at an existing conda (or mamba) environment by name or prefix:

```toml
[environment]
kind = "conda"
name = "demo-env"
# or
# path = "/opt/conda/envs/demo-env"
```

Behavior:

- If `path` is provided, `arxpm` uses `<path>/bin/python` directly.
- Otherwise `arxpm` invokes
  `conda run -n <name> python -c "import sys; print(sys.executable)"` to locate
  the interpreter, then installs via `uv pip install --python <interp>`.
- `conda` must be on PATH when only `name` is provided.

## Why uv?

`uv` is used as the package installer for every strategy. It is fast, it does
not require an active venv (it accepts `--python <interp>`), and it is a single
static binary. `arxpm healthcheck` reports whether `uv` is reachable on your
PATH.

## Tooling not managed by arxpm

`arxpm publish` and `arxpm pack` use `python -m build` and `python -m twine`
from the _outer_ interpreter that is running `arxpm`. They never install build
tooling into your project environment. `build` and `twine` are declared as
runtime dependencies of `arxpm` itself, so they are always available wherever
`arxpm` is installed.
