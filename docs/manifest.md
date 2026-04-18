# Manifest

Arx projects are described by `.arxproject.toml`.

## Minimal Layout

```toml
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"

dependencies = []

[build]
src_dir = "src"
entry = "main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
```

## Source Layout

`build.src_dir` names the directory where your `.x` sources live, relative to
the project root. It defaults to `"src"` (the recommended layout). `build.entry`
is **always interpreted relative to `src_dir`**, so with the default layout a
file at `src/main.x` is spelled `entry = "main.x"`.

Override `src_dir` when your project uses a different convention — for example,
`src_dir = "."` to keep sources at the project root, or `src_dir = "lib"` to use
a `lib/` folder. Cross-project tooling (`arxpm build`, `arxpm pack`) uses
`<src_dir>/<entry>` internally and strips `src_dir` when bundling for
publication, so published modules always appear flat under their package name.

## Dependency Forms (v0)

Runtime dependencies live in the `project.dependencies` array and use PEP
508-style strings. `arxpm` supports three shapes:

1. Registry (bare name):

```toml
dependencies = [
  "pyyaml",
]
```

2. Local path:

```toml
dependencies = [
  "mylib @ ../mylib",
]
```

3. Git:

```toml
dependencies = [
  "utils @ git+https://example.com/utils.git",
]
```

Version solving is intentionally out of scope in v0. During `arxpm install`,
registry dependencies are installed with `uv pip install <name>`, path
dependencies with `uv pip install <path>`, and git dependencies with
`uv pip install git+<url>`.

## Dev Dependencies

Tools that are only needed while developing the project (test runners, task
runners, linters) go in a dedicated `[arxpm.dependencies-dev]` table and are
only installed when you opt in with `arxpm install --dev`:

```toml
[arxpm.dependencies-dev]
dependencies = [
  "makim",
]
```

## Environment

The `[environment]` table controls how `arxpm install` obtains a Python
environment for the project. It is optional — when absent, `arxpm` behaves as if
`kind = "managed-venv"` with `path = ".venv"` had been declared.

```toml
[environment]
kind = "managed-venv"      # managed-venv | existing-venv | conda
path = ".venv"              # optional for managed-venv and conda
name = "my-conda-env"       # required when kind = "conda" and no path
```

Validation rules:

- `managed-venv`: `name` is not allowed. `path` defaults to `".venv"`.
- `existing-venv`: `path` is required, `name` is not allowed. The path must
  resolve to an existing venv at `arxpm install` time (not at parse time, so
  manifests stay portable).
- `conda`: at least one of `name` or `path` is required.
- Any other `kind` value is rejected with a manifest error.

See [Environments](environments.md) for how each strategy behaves at runtime.
