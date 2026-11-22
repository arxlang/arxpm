---
name: agent-authoring
description:
  Create or maintain portable arxpm Agent Skills in `.agents/skills`, with
  narrow triggers, minimal duplication and safe tool permissions.
---

# Create and maintain effective arxpm skills

**Use for adding or revising
`.agents/skills/**/SKILL.md`.** Do not create `.github/agents/` or
platform-specific Copilot configuration.

## What a good skill contains

- YAML frontmatter whose `name` exactly matches the lowercase-hyphenated
  directory and a concise `description` that states use.
- Verified `arxpm` paths, `.makim.yaml` tasks, CI behavior, and package
  contracts.
- A short workflow with preconditions, evidence, decision points, validation,
  failure paths, and stop conditions.
- Relative links only to existing files inside `.agents/skills/`.
- No duplicate procedures already owned by `AGENTS.md`.

## Authoring procedure

1. Inspect `AGENTS.md`, `src/arxpm/`, `tests/`, `examples/`, `.makim.yaml`,
   `pyproject.toml`, pre-commit, and the relevant workflow.
2. Start with the smallest complete workflow. Avoid repository-irrelevant
   generic advice.
3. Adapt commands and repo names to `arxlang/arxpm`; never copy compiler,
   monorepo, or native-runtime ownership procedures.
4. Use only facts from checked files. State when a tool or remote result is
   unavailable.
5. Review for stale paths, accidental mutation instructions, secret exposure,
   broad permissions, and unverified claims.
6. Validate frontmatter, Markdown, relative links, formatting, and the relevant
   representative command.

**Exit:** a skill guides a safe, verifiable result without unnecessary files or
platform-specific configuration.
