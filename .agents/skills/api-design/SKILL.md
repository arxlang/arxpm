---
name: api-design
description:
  Design minimal, consistent arxpm Python APIs and CLI surfaces with clear
  semantics, typing, exports and validation.
---

# Design one coherent arxpm API

**Use for changes to public Python functions, classes, Typer commands, options,
models, exports, or manifest behavior.** Apply
[minimal-change](../minimal-change/SKILL.md) and
[python-code-style](../python-code-style/SKILL.md).

## API design steps

1. Find the nearest comparable implementation in `src/arxpm/`, inspect real
   callers in `tests/`, and identify the ownership layer: `manifest.py`,
   `models.py`, `layout.py`, `environment.py`, `project.py`, `healthcheck.py`,
   `cli.py`, or `credentials.py`.
2. Start with a common-case usage example. Verify invalid values and existing
   `ArxpmError` subclasses, not a generic catch-all.
3. Choose one canonical entry point. Do not add alias methods or optional
   booleans when a typed existing value or explicit mode is sufficient.
4. Define complete annotations, defaults, valid combinations, output/status
   behavior, filesystem effects, and subprocess failure policy.
5. Keep CLI parsing in `cli.py` and manifest/environment logic in its owning
   module. Avoid Typer callbacks that hide project-state validation.
6. Update relevant exports, models, docs, and tests when public behavior
   changes. Preserve existing names unless a real defect or usability contract
   requires renaming.

## Validation

Verify common usage, invalid arguments, environment/manifest edge cases, and
only the distinct boundary behavior not already covered.

Run:

```bash
pytest -q tests/test_<area>.py
makim tests.unit
makim tests.linter
```
