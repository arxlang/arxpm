# Multi-file Projects

An Arx project can be composed of several `.x` files that refer to each other
via `import` statements. Only the entry module is named in `.arxproject.toml` —
the compiler discovers sibling modules on the filesystem at build time.

## Layout

```
multi-module/
├── .arxproject.toml
└── src/
    ├── main.x
    ├── math_utils.x
    └── string_utils.x
```

`.arxproject.toml`:

```toml
[project]
name = "multi-module"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
```

The manifest lists only `src/main.x`. `arxpm build` invokes the compiler as
`arx src/main.x --output-file build/multi-module`; the compiler resolves
`import` statements against sibling files.

## Import syntaxes

The following forms are accepted in any `.x` file:

```
import std.math
import std.math as math

import sin from std.math
import sin as sine from std.math

import (sin, cos, tan as tangent) from std.math

import (
  sin,
  cos,
  tan as tangent,
) from std.math
```

Dotted names resolve to directories: `import std.math` looks for `std/math.x`
under the entry file's directory and its ancestors.

## Calling imported functions

`src/math_utils.x`:

```
fn add(a: i32, b: i32) -> i32:
  return a + b;
```

`src/string_utils.x`:

```
fn greet(name: string) -> string:
  return "Hello, " + name + "!";
```

`src/main.x`:

```
import add from math_utils
import greet from string_utils

fn main() -> i32:
  print(greet("Arx"));
  print(add(2, 3));
  return 0;
```

Running this project with `arxpm run` prints:

```
Hello, Arx!
5
```

A working copy of this project lives at
[`examples/multi-module/`](https://github.com/arxlang/arxpm/tree/main/examples/multi-module).

## Packaging

`arxpm pack` and `arxpm publish` bundle every `*.x` / `*.arx` file under the
project root (excluding `build/`, `dist/`, virtualenvs, and caches). Multi-file
projects publish without additional configuration.
