# Environments

`arxpm` does not bundle its own Python environment. Every project declares how
its Python environment should be provided, and `arxpm` uses
[`uv`](https://github.com/astral-sh/uv) to install packages into the interpreter
you point it at.

Three strategies are supported out of the box, each declared in
`.arxproject.toml` via the `[environment]` table.

## Strategy 1 — `venv` (default)

`arxpm` uses a virtual environment declared by `kind = "venv"`. When `path` is
omitted, `arxpm` treats it as a project-local `.venv` and creates it with
`uv venv` if needed.

```toml
[environment]
kind = "venv"
path = ".venv"   # optional; defaults to ".venv"
```

Behavior:

- `arxpm install` runs `uv venv <path>` if the venv does not yet exist, then
  `uv pip install --python <venv>/bin/python ...` for your dependencies.
- `arxpm run` and `arxpm build` do not touch the venv; they invoke the `arx`
  compiler directly from the outer PATH.

Omit the whole `[environment]` section for the simplest projects — the defaults
match what you'd write by hand.

## Strategy 2 — `conda`

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

## Strategy 3 — `system`

Use the Python interpreter that is already running `arxpm`.

```toml
[environment]
kind = "system"
```

Behavior:

- `arxpm install` installs packages into the current Python environment using
  `uv pip install --python <sys.executable> ...`.
- `path` and `name` are not allowed for this mode.

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
