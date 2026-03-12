# Manifest

Arx projects are described by `arxproj.toml`.

## Minimal Layout

```toml
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
out_dir = "build"

[dependencies]

[toolchain]
compiler = "arx"
linker = "clang"
```

## Dependency Forms (v0)

`arxpm` supports three dependency shapes:

1. Registry placeholder:

```toml
http = { source = "registry" }
```

2. Local path:

```toml
mylib = { path = "../mylib" }
```

3. Git:

```toml
utils = { git = "https://example.com/utils.git" }
```

Version solving is intentionally out of scope in v0. During `arxpm install`,
registry dependencies are installed with `pip install <name>`, path dependencies
with `pip install <path>`, and git dependencies with `pip install git+<url>`.
