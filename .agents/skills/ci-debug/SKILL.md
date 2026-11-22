---
name: ci-debug
description:
  Investigate arxpm GitHub Actions and Makim failures by finding the first root
  failure and making the narrowest verified fix.
---

# Diagnose arxpm CI failures

**Use for a failed GitHub Actions run or Makim task.** Read the exact workflow,
job, step, commit SHA, and log before concluding a cause.

## Locate and classify

1. Capture branch/PR head SHA, Python version, OS, workflow revision, and the
   failing step.
2. Compare the run with `.github/workflows/main.yaml`,
   `.github/workflows/docs.yaml`, `.github/workflows/release.yaml`, and
   `.makim.yaml`.
3. Determine the category:
   - unit/test/coverage regression
   - example smoke or missing `arx`/`uv` tool
   - Poetry or environment installation failure
   - pre-commit/Ruff/mypy/Douki/shellcheck/bandit/mccabe failure
   - docs/build or release-workflow configuration issue
   - infrastructure flakiness supported by repeated evidence
4. Check baseline versus the proposed commit. Do not retry unrelated jobs merely
   to manufacture a green result.

## Verify narrowly

```bash
pytest -q tests/test_<area>.py
makim tests.unit
makim tests.smoke
makim tests.linter
makim docs.build
```

Use the smallest failing command first. Run `makim tests.ci` only when an
aggregate check is necessary.

| Failure        | Investigate                                     | Avoid                                    |
| -------------- | ----------------------------------------------- | ---------------------------------------- |
| `tests.unit`   | focused test, coverage, fixture, Python matrix  | lowering the 90% gate                    |
| `tests.smoke`  | `uv`, `arx`, temp example copy, manifest/layout | modifying examples to hide failure       |
| Pre-commit     | actual hook output and filename                 | broad formatting outside the change      |
| Poetry install | manifest, lock/environment setup, Python matrix | blind dependency upgrades                |
| Release/docs   | workflow event, secrets/permissions, Makim task | publishing or granting broad permissions |

Report exact URL/job/SHA, first failure, evidence, minimal fix, commands, and
remaining unknowns. Never invent a root cause.
