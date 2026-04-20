# Multi-file Projects

An Arx project can be composed of several `.x` files that refer to each other
via `import` statements. `arxpm` now resolves the package root and passes an
explicit file path to `arx`.

## Layout

```
multi-module/
├── .arxproject.toml
└── src/
    └── multi_module/
        ├── __init__.x
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
package = "multi_module"
mode = "app"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
```

`arxpm build` invokes the compiler as:

```text
arx src/multi_module/main.x --output-file build/multi_module
```

Sibling imports still work from inside the package root.

## Calling imported functions

`src/multi_module/math_utils.x`:

```
fn add(a: i32, b: i32) -> i32:
  return a + b;
```

`src/multi_module/string_utils.x`:

```
fn greet(name: string) -> string:
  return "Hello, " + name + "!";
```

`src/multi_module/main.x`:

```
import add from math_utils
import greet from string_utils

fn main() -> i32:
  print(greet("Arx"));
  print(add(2, 3));
  return 0;
```

## Packaging

`arxpm pack` and `arxpm publish` bundle every `*.x` / `*.arx` file under the
resolved source root, preserving the package-relative layout.
