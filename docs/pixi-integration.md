# Pixi Integration

`arxpm` uses Pixi as backend infrastructure and keeps a narrow ownership scope.

## Ownership Boundary

`arxpm` does not own all of `pixi.toml`. It only manages:

- required toolchain dependencies (`python`, `clang`)
- the `tool.arxpm` section used to track managed fields

Unrelated user sections such as tasks and features are preserved.

## Manifest Behavior

- If `pixi.toml` is missing, `arxpm` creates a minimal manifest.
- New manifests use `[workspace]` and include dependencies plus `[tool.arxpm]`.
- If `pixi.toml` exists, `arxpm` updates only missing managed pieces.

## Commands

The integration currently shells out to:

- `pixi install`
- `pixi run ...`

All external command execution is centralized through `external.py`.
