---
name: douki-docstrings
description:
  Write and validate arxpm Python Douki docstrings and `.x` example module
  docstrings with minimal documentation churn.
---

# Maintain arxpm source contracts

**Use for public Python symbols, `.x` smoke fixtures, and documentation contract
changes.** Apply [minimal-change](../minimal-change/SKILL.md).

## Python docstrings

`src/arxpm/` uses Douki-style triple-quoted docstrings with fields such as
`title`, `summary`, `parameters`, `attributes`, and `returns`.

```python
def validate_name(name: str) -> str:
    """
    title: Validate a requested name.
    parameters:
      name:
        type: str
    returns:
      type: str
    """
    if not name:
        raise ValueError("name must not be empty")
    return name
```

Preserve existing correct descriptions. Update a docstring when signature,
meaning, parameters, return behavior, or safety contract changes. Do not reword
unrelated documentation.

The pre-commit `douki` hook runs `douki sync` across repository files.

## `.x` smoke fixtures

Committed `.x` files under `examples/` begin at line 1, column 1 with a
triple-backtick Douki module block:

````text
```
title: Example module
summary: Describe the module.
```
````

Preserve existing two-space indentation and module/package layout. Smoke tests
copy examples to temporary directories and run `healthcheck`, `install`,
`build`, and app `run` workflows.

## Documentation decisions

| Change                              | Action                                                 |
| ----------------------------------- | ------------------------------------------------------ |
| Internal behavior, unchanged API    | No guide change unless a source contract is inaccurate |
| Public CLI/model/environment change | Update the owning source docstring and smallest guide  |
| New user workflow or restriction    | Extend an existing `docs/` page                        |
| Generated API output                | Keep source authoritative                              |

Run `makim tests.linter` for source/docstring lint and `makim docs.build` when
MkDocs output is affected.
