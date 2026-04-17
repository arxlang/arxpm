# Local Packages

A library and its consumer can live side by side during development so the
consumer imports the library's functions directly. This page describes the
layout that works with the current Arx toolchain and the boundary that still
exists around installed packages.

## Supported layout: sibling workspace

```
workspace/
├── local_lib/
│   ├── .arxproject.toml
│   ├── pixi.toml
│   ├── local_lib.x
│   └── stats.x
└── local-consumer/
    ├── .arxproject.toml
    ├── pixi.toml
    └── src/
        └── main.x
```

The library's directory name **must** equal the dotted prefix used by its
consumers. `import sum2 from local_lib.stats` resolves to
`<ancestor>/local_lib/stats.x`, so the directory is named `local_lib/` and
`stats.x` lives at its top level.

`local_lib/stats.x`:

```
fn sum2(a: i32, b: i32) -> i32:
  return a + b;
```

`local-consumer/src/main.x`:

```
import sum2 from local_lib.stats

fn main() -> i32:
  print(sum2(2, 3));
  return 0;
```

Running `arxpm run` inside `local-consumer/` prints `5`.

## How resolution actually works

The Arx compiler's file resolver walks the ancestors of the entry file looking
for the first directory that contains the imported module. For the layout above,
the ancestors of `local-consumer/src/main.x` include `workspace/`, which is also
a parent of `local_lib/`. That shared ancestor is what lets the import resolve.

This means cross-project imports work as long as the consumer and the library
share a common parent directory on disk — a sibling workspace.

## Working examples

- [`examples/local_lib/`](https://github.com/arxlang/arxpm/tree/main/examples/local_lib)
- [`examples/local-consumer/`](https://github.com/arxlang/arxpm/tree/main/examples/local-consumer)

Copy both directories so they sit next to each other, then:

```
cd local-consumer
arxpm install
arxpm build
arxpm run
```

Expected stdout: `5`.

## Current limits

- **No pip-installed library imports.** `arxpm pack` produces a wheel that
  bundles every `.x` / `.arx` source, and pip-installing that wheel into the
  consumer's Pixi environment works — but the Arx compiler does not read from
  Python's `site-packages`. Imports of a library that exists only as an
  installed wheel will fail with `Unable to resolve module`.
- **No path-dep bridge.** Declaring `local_lib = { path = "../local_lib" }`
  under `[dependencies]` causes `arxpm install` to invoke
  `pip install ../local_lib`, which fails because a vanilla Arx project has no
  `pyproject.toml`. For now, leave `[dependencies]` empty for local libraries
  and rely on the sibling workspace layout above.
- **No version solving or editable installs.** Local development uses files on
  disk; there is no registry, lockfile, or `-e` workflow today.

## Packaging local libraries

`arxpm pack` and `arxpm publish` still bundle every `.x` / `.arx` file under the
project root, so libraries can be published to PyPI once the compiler gains a
`site-packages` search path. Until then, publishing is only useful for
distribution or archival — consumers building against a wheel today will not
find the imported modules.
