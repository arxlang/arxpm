---
name: python-code-style
description:
  Apply arxpm Python conventions, including strict typing, Ruff, Douki
  docstrings, guard clauses and focused validation.
---

# Python implementation conventions for arxpm

**Use for Python edits and reviews.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Types and docstrings

- Annotate every argument and return where practical.
- Strict mypy uses `mypy_path = "src"`, targets Python 3.11, and checks `src`.
- Ruff targets Python 3.11, uses 79-character lines, and selects `E`, `F`, `I`,
  `UP`, and `B`.
- Preserve existing Douki YAML docstrings and update them only when a public
  signature or meaning changed.
- `atpublic`, `typeguard`, and `plum-dispatch` are not actual arxpm conventions.
  Do not add them.

```python
def checked_divisor(value: int | None) -> int:
    """
    title: Validate a divisor.
    parameters:
      value:
        type: int | None
    returns:
      type: int
    """
    if value is None:
        raise ValueError("missing divisor")
    if value == 0:
        raise ValueError("divisor must not be zero")
    return value
```

## Control flow and errors

- Prefer validation-first guard clauses.
- Keep exceptions explicit and local to manifest, environment, credential,
  filesystem, or subprocess ownership.
- Do not swallow `ArxpmError` subclasses or command failures.
- Do not add reflective `getattr` code where a typed interface already exists.
- Use existing protocols/classes rather than speculative abstraction.

## Verification

```bash
pytest -q tests/test_<area>.py
ruff format --check src tests
ruff check src tests
mypy .
makim tests.linter
```
