# Local Packages

A library and its consumer can live side by side on disk and be wired together
with a path dependency. `arxpm install` handles the packaging / install / link
step so the Arx compiler finds the library's modules at build time.

## Supported layout

Arx projects default to a `src/` source root. The library's `.x` sources sit
under `src/`, the consumer's sources sit under its own `src/`, and each side
declares `src_dir = "src"` in `[build]`:

```
workspace/
├── local_lib/
│   ├── .arxproject.toml
│   └── src/
│       ├── local_lib.x
│       └── stats.x
└── local-consumer/
    ├── .arxproject.toml
    └── src/
        └── main.x
```

The library's `project.name` becomes the Arx module name used by consumers.
`arxpm pack` strips the `src_dir` prefix when bundling, so the wheel lays the
sources out flat under `<package>/`. That means
`import sum2 from local_lib.stats` resolves to the `stats.x` file inside the
package directory named `local_lib/` (not `local_lib/src/stats.x`).

### Customizing the source directory

`src_dir` defaults to `"src"` but you can override it per project — for example,
a library that keeps its sources at the project root would declare
`src_dir = "."`, and one that uses a `lib/` root would declare
`src_dir = "lib"`. `entry` is always interpreted **relative to `src_dir`**, so
the entry path passed to the compiler is `<src_dir>/<entry>`.

## Declaring the dependency

`local-consumer/.arxproject.toml`:

```toml
[project]
name = "local-consumer"
version = "0.1.0"
edition = "2026"

dependencies = [
  "local_lib @ ../local_lib",
]

[build]
src_dir = "src"
entry = "main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
```

The name on the left of `@` **must** match the library's Arx module name
(derived from its `project.name`, normalized to a Python identifier).
`arxpm install` rejects mismatched names rather than producing a silent failure
at build time.

## What `arxpm install` does for an Arx path dependency

For each `project.dependencies` entry of the form `<name> @ <path>` where
`<path>` points at a directory containing `.arxproject.toml`, `arxpm install`:

1. Packs the library (runs `arxpm pack` on that path) to produce a wheel that
   bundles every `.x` / `.arx` source under the library's `src_dir`, flattened
   to the package root.
2. Installs the wheel into the consumer's Python environment via
   `uv pip install --python <interp> --force-reinstall --no-deps <wheel>`, so
   the library lands at `<env>/lib/pythonX/site-packages/<module_name>/`.
3. Creates a symlink `<consumer>/<module_name>` pointing at the installed
   directory. The Arx compiler's resolver walks the ancestors of the entry file
   looking for `<module_name>/<sub>.x`, so the symlink at the consumer's project
   root is what lets the import succeed.

Commit the `.arxproject.toml` entry; ignore the generated symlink:

```
# local-consumer/.gitignore
/local_lib
```

## Example

The `examples/` directory ships a working pair:

- [`examples/local_lib/`](https://github.com/arxlang/arxpm/tree/main/examples/local_lib)
- [`examples/local-consumer/`](https://github.com/arxlang/arxpm/tree/main/examples/local-consumer)

Copy them so they sit next to each other, then from the consumer:

```
cd local-consumer
arxpm install
arxpm build
arxpm run
```

Expected stdout: `5`.

## Current limits

- **Compiler resolution is local, not site-packages.** The Arx compiler's
  `FileImportResolver` only searches CWD and ancestors of the input files — it
  does not read from `site-packages` directly. The symlink step is what bridges
  the installed wheel back into the consumer's ancestor tree.
- **Path deps only; no registry or git.** `<name> @ git+...` dependencies still
  go straight through `uv pip install` and bring no cross-compile support today
  — only `<name> @ <path>` entries pointing at an Arx project trigger the
  pack/install/link flow.
- **No version solving or editable installs.** Every `arxpm install` re-packs
  the library and reinstalls the wheel. For iterative library development, edit
  sources and re-run `arxpm install` in the consumer.
- **No circular dependencies.** A and B cannot depend on each other.
