---
name: open-pr
description:
  Open or update a scoped arxlang/arxpm pull request with a Conventional Commit
  title and explicit verification.
---

# Open or update an arxpm PR

**Use only when explicitly asked to create, push, open, or update a PR.** Apply
[minimal-change](../minimal-change/SKILL.md) and
[pr-review](../pr-review/SKILL.md). Never infer authority to merge, publish,
tag, or force-push.

## Preflight

1. Identify upstream `arxlang/arxpm`, the requested fork, branch, base ref, and
   head SHA.
2. Inspect `git status`, intended diff, and working tree. Do not overwrite
   unrelated changes.
3. Run focused checks and review the complete branch diff against the upstream
   base.

## PR quality gate

- Only requested implementation, required tests, and true contract updates.
- No duplicate tests, generated docs, incidental formatting, dependency lock
  edits, benchmarks, secrets, or unrequested CI changes.
- Title uses Conventional Commit format, for example
  `fix(project): preserve environment on install failure`.
- Body contains goal, changes, verification, and limitations.
- Link an issue only when it exists; do not invent one.

## Remote actions

Commit, push, or open/update only with authorization. Never merge, tag, release,
publish, modify unrelated issues, or force-update refs. If permissions prevent
fork PR creation, leave the branch intact and provide the exact compare/create
link.

Done: report branch, base SHA, PR URL or compare URL, checks, and blockers.
