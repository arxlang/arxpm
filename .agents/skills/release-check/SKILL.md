---
name: release-check
description:
  Check arxpm semantic-release readiness, package metadata, workflow permissions
  and artifacts without publishing.
---

# Review arxpm release readiness

**Use for packaging or publishing-workflow questions.** By default this skill
does not publish, tag, create commits, or edit remote state.

## Evidence to collect

- `pyproject.toml`: package version, dependencies, Python bounds, scripts, build
  backend, and dev tools.
- `.releaserc.json`: branch, replacement plugin, changelog, build/publish,
  GitHub asset, and git commit assets.
- `.github/workflows/main.yaml`, `docs.yaml`, and `release.yaml`: events,
  matrices, permissions, secrets, and Makim tasks.
- `poetry.lock` when dependency changes are under review; never hand-edit it.
- `.makim.yaml`: `release.dry`, `release.ci`, unit, smoke, linter, and docs
  tasks.

## Checklist

1. Confirm project version and replacement targets remain consistent.
2. Confirm Python bounds and CI matrix agree.
3. Confirm `poetry build`/`poetry publish` and release assets match package
   metadata.
4. Confirm normal workflow events perform dry release, while manual dispatch
   performs live release.
5. Confirm required secrets and permissions are absent from pull requests when
   appropriate; do not treat a secretless PR run as proof of live
   authentication.
6. Check partial-publish, tag, commit, and rerun behavior before recommending
   changes.
7. Use existing tasks:

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim release.dry
makim docs.build
```

Do not run `makim release.ci` or publish unless the user explicitly authorizes
the live operation.

## Findings format

- **Blockers:** evidenced version, artifact, permission, or workflow defect.
- **Non-blocking:** useful narrow reliability improvement.
- **Verified:** exact checks executed.
- **Unverified:** live-publish-only behavior.
