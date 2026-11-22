---
name: minimal-change
description:
  Keep arxpm changes and PRs minimal without compromising correctness; avoid
  incidental refactors, duplicate tests and unnecessary tooling.
---

# Minimal necessary change

**Use for every implementation, plan, test, review, or documentation task.**
This scope-control procedure complements `AGENTS.md`.

## First establish the change

1. Read the request and current behavior. Separate explicitly requested work
   from speculative improvements.
2. Inspect only the relevant source, tests, fixtures, Makim task, and workflow.
3. Reuse direct code and established extension points.
4. Identify the verification that proves the result.
5. Compare the final diff with the acceptance criteria.

## Decision table

| Proposed change      | Normally do                 | Expand only when                              |
| -------------------- | --------------------------- | --------------------------------------------- |
| Rename               | Preserve it                 | Meaning or correctness requires it            |
| Restructure          | Keep local structure        | Current organization prevents a correct fix   |
| Add helper           | Reuse direct code           | Multiple real callers need it                 |
| Change docstring     | Leave it unchanged          | Signature or meaning changed                  |
| Add test             | Search existing tests first | Distinct behavior lacks coverage              |
| Add docs page        | Usually avoid               | Public workflow needs existing-guide coverage |
| Change CI/dependency | Usually avoid               | Required to verify or deliver the change      |

## Implementation rules

- Use validation-first guard clauses and existing typed exceptions.
- Preserve subprocess, environment, credential, and filesystem boundaries.
- Do not lower coverage, suppress diagnostics, or skip error cleanup.
- Do not format untouched code or add "while here" refactors.
- Stop when the behavior works and relevant checks pass or blockers are
  explicitly reported.

## Review red flags

- Broad rewrites unrelated to the request.
- Duplicate test matrix or fixture.
- Expanding a small PR into speculative milestones.
- A passing implementation with unrequested documentation or CI changes.
