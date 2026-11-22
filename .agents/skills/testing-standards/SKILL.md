---
name: testing-standards
description:
  Select and reuse existing arxpm tests, adding only distinct necessary coverage
  and targeted verification.
---

# Select meaningful arxpm test coverage

**Use whenever adding, changing, or reviewing tests.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Pre-test audit

1. Search `tests/`, existing fixtures, parametrization, and integration markers
   for the invariant.
2. If existing coverage already fails when behavior returns, do not add a
   duplicate test.
3. Extend the closest test if one case/assertion is enough.
4. Add a new test only for a distinct owner or failure mode.

## Test map

| Area                   | Preferred coverage                                       |
| ---------------------- | -------------------------------------------------------- |
| Manifest/models        | `tests/test_manifest.py`, `tests/test_models.py`         |
| CLI                    | `tests/test_cli.py`, `test_main.py`                      |
| Environment/subprocess | `tests/test_environment.py`, `test_external.py`          |
| Project workflows      | `tests/test_project.py`, `test_healthcheck.py`           |
| Credentials            | `tests/test_credentials.py`                              |
| Example projects       | `tests/test_examples.py`, `test_examples_integration.py` |

The integration marker is `integration`; tests requiring `arx` and `uv` are
separate from unit coverage.

## Verification

```bash
pytest -q tests/test_<area>.py
pytest -m integration -q
makim tests.unit
makim tests.smoke
makim tests.linter
```

`tests.unit` enforces `--cov-fail-under=90`. Coverage is an additional evidence
layer, not a substitute for assertions.
