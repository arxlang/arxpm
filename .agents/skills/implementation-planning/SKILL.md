---
name: implementation-planning
description:
  Plan a feasible, reviewable arxpm implementation or refactor with acceptance
  criteria and existing verification.
---

# Plan a one-week arxpm implementation

**Use when asked for milestones, a feature breakdown, or substantial
refactoring.** Always apply [minimal-change](../minimal-change/SKILL.md).

## Planning protocol

1. **Goal:** State precisely what changes for users or contributors.
2. **Current implementation:** Inspect relevant `src/arxpm/`, `tests/`,
   `examples/`, `.makim.yaml`, and workflows before proposing design.
3. **Acceptance criteria:** List 2–5 observable behaviors including critical
   error and compatibility behavior.
4. **Smallest vertical slice:** Include CLI, manifest/layout, environment,
   packaging, tests, and docs only where the contract requires them.
5. **Execution:** Use 3–7 meaningful steps, not file-by-file task lists.
6. **Verification:** Name focused pytest tests and existing Makim tasks.
7. **Risks:** Report immediate blockers and intentional exclusions only.

## Output format

```markdown
## Goal

<one sentence>

## Acceptance criteria

- <observable behavior>

## Implementation

1. <owner and code change>
2. <necessary integration>
3. <verification>

## Risks / out of scope

<only meaningful items>
```

Avoid Gantt charts, invented estimates, new plan files, benchmarks, speculative
CI jobs, and broad rewrites.
