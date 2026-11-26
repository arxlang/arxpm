---
name: pr-review
description:
  Review arxpm PRs or local diffs for correctness, scope, test quality and
  documentation churn. Read-only unless review submission or editing is
  explicitly authorized.
---

# Review an arxpm pull request

**Use for PR, branch, or local-diff review.** This skill is read-only unless the
user explicitly asks to submit a GitHub review or edit code. Apply
[minimal-change](../minimal-change/SKILL.md).

## Inputs and scope

- Inspect exact base/head SHAs, diff, commits, body, conversations, review
  comments, and CI for a PR target.
- For local work, inspect `git status`, the relevant base diff, staged changes,
  and uncommitted changes separately.
- Never assume a branch contains only one commit or that CI replaces reasoning.

## Read and reason

1. State the intended contract and affected modules.
2. Trace CLI through `cli.py`, models/manifests/layout, environment/project
   workflows, subprocesses, and credential handling.
3. Probe filesystem, environment, manifest, Python 3.10–3.14, missing `uv` or
   `arx`, subprocess failure, credential fallback, and packaging edge cases.
4. Compare tests with existing coverage. A new function or file is not valuable
   by itself.
5. Check scope: unrelated formatting, renames, duplicate tests, docs, new CI,
   dependency changes, and generated artifacts.

## Severity and report

- P0/P1: unsafe behavior, credential/secrets exposure, destructive filesystem
  behavior, broken environment/package workflow, or missing critical contract.
- P2: reproducible regression or essential behavior-specific test.
- Non-blocking: useful maintainability or scope reduction without correctness
  impact.

Each finding needs location, impact, evidence, and a minimal correction.

```markdown
## Blocking findings

- [P1] <finding> — path:line Contract / impact / evidence / correction

## Non-blocking

- <only useful follow-up>

## Verification and uncertainties

- Confirmed: <actual evidence>
- Not verified: <specific risk>

## Recommendation

Request changes / No blockers / Unable to conclude
```

Do not post, label, or modify a PR without explicit authorization.
