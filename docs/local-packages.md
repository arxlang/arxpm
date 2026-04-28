# Local Packages

A library and its consumer can live side by side on disk and be wired together
with a path dependency. `arxpm install` handles the packaging / install / link
step so the Arx compiler finds the library's modules at build time.

Published Arx packages use the same runtime shape: wheels and source
distributions include `.arxproject.toml` plus `*.x` / `*.arx` source files.
After `uv` installs registry, Git, or local wheel dependencies, `arxpm install`
links any installed Arx package sources in the dependency closure into the
consumer project root.

## Supported layout

```
workspace/
├── local_lib/
│   ├── .arxproject.toml
│   └── src/
│       └── local_lib/
│           ├── __init__.x
│           └── stats.x
└── local-consumer/
    ├── .arxproject.toml
    └── src/
        └── local_consumer/
            ├── __init__.x
            └── main.x
```

Library manifest:

```toml
[project]
name = "local_lib"
version = "0.1.0"

[build]
mode = "lib"
```

Consumer manifest:

```toml
[project]
name = "local-consumer"
version = "0.1.0"

dependencies = [
  "local_lib @ ../local_lib",
]

[build]
package = "local_consumer"
mode = "app"
```

The dependency name on the left of `@` must match the library's resolved Arx
package name. `arxpm install` rejects mismatches instead of guessing.

## What `arxpm install` does

For each `project.dependencies` entry of the form `<name> @ <path>` where
`<path>` points at a directory containing `.arxproject.toml`, `arxpm install`:

1. Validates the library layout.
2. Packs the library to produce a wheel that bundles its `.x` / `.arx` sources.
3. Installs the wheel into the consumer's Python environment with `uv`.
4. Creates a symlink `<consumer>/<package>` pointing at the installed package
   directory so Arx import resolution can find it locally.

For registry, Git, or wheel dependencies, `arxpm install` first lets `uv`
install the requested packages and their metadata-declared transitive
dependencies. It then inspects the installed dependency closure for bundled
`.arxproject.toml` files and links each discovered Arx source root as
`<consumer>/<package>`. Normal Python-only dependencies are left untouched.

For packaging, `arxpm pack` and `arxpm publish` render dependencies into the
generated `pyproject.toml`. Registry dependencies remain plain package names,
Git dependencies are rendered as `name @ git+...`, and path dependencies are
rendered by name so published packages can resolve them from the target package
index.
