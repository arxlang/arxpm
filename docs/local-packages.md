# Local Packages

A library and its consumer can live side by side on disk and be wired together
with a path dependency. `arxpm install` handles the packaging / install / link
step so the Arx compiler finds the library's modules at build time.

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
