# Manifest

Arx projects are described by `.arxproject.toml`.

## Build contract

```toml
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"
requires-arx = ">=1.0"

[build-system]
dependencies = [
  "arxlang>=1.0",
]

[build]
src_dir = "src"
out_dir = "build"
package = "hello_arx"
mode = "app"
```

`[project]` supports:

- `name`: required project name
- `version`: required project version
- `edition`: optional Arx edition
- `requires-arx`: optional Arx compiler version specifier
- `dependencies`: optional runtime dependency strings

`[build-system]` supports:

- `dependencies`: optional Python requirement strings used to prepare the build
  environment. If omitted, `arxpm` installs the default Arx compiler package.

When `project.requires-arx` is set and no explicit `arxlang` build dependency is
listed, `arxpm` prepends `arxlang<specifier>` to the effective build-system
dependencies. An explicit `arxlang` entry is preserved as written.

`[build]` supports:

- `src_dir`: optional, defaults to `"src"`
- `out_dir`: optional, defaults to `"build"`
- `package`: optional, defaults to `project.name`
- `mode`: optional, `"lib"` or `"app"`

`[build].entry` was removed. `arxpm` rejects manifests that still declare it.
`[toolchain]` was removed; declare compiler/build requirements in
`[build-system].dependencies`.

## Source layout

`arxpm` resolves the effective layout from the project root:

- `source_root = <project>/<src_dir>`
- `package_root = <source_root>/<package>`
- `init_file = <package_root>/__init__.x`
- `main_file = <package_root>/main.x`

`__init__.x` is always required.

If `mode` is omitted, `arxpm` infers it from the filesystem:

- if `main.x` exists, the project is treated as an app
- otherwise, the project is treated as a library

Validation rules:

- `source_root` must exist
- `package_root` must exist
- `__init__.x` must exist
- app projects must contain `main.x`
- lib projects must not contain `main.x`

Package names must match `^[A-Za-z_][A-Za-z0-9_]*$`. If `project.name` is not a
valid package identifier, set `[build].package` explicitly instead of relying on
normalization.

## Examples

Library:

```toml
[project]
name = "astx"
version = "0.1.0"

[build]
mode = "lib"
```

App:

```toml
[project]
name = "myapp"
version = "0.1.0"

[build]
mode = "app"
```

Package override:

```toml
[project]
name = "my-project"
version = "0.1.0"

[build]
package = "my_project"
mode = "lib"
```

## Runtime dependencies

Runtime dependencies live in the `project.dependencies` array and use PEP
508-style strings. `arxpm` supports three shapes:

1. Registry:

```toml
dependencies = [
  "pyyaml",
  "requests>=2.31,<3",
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

## Dependency groups

Non-runtime workflow dependencies such as test, lint, and docs tools live in the
top-level `[dependency-groups]` table.

```toml
[dependency-groups]
dev = [
  "pytest",
  "ruff",
]
```

## Environment

The `[environment]` table controls how `arxpm install` obtains a Python
environment for the project. It is optional — when absent, `arxpm` behaves as if
`kind = "venv"` with `path = ".venv"` had been declared.
