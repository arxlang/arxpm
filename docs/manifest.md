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
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
```

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
registry dependencies are installed with `pip install <name>`, path dependencies
with `pip install <path>`, and git dependencies with `pip install git+<url>`.

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
