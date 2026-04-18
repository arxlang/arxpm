# Roadmap

## `arx.settings` alignment

The manifest-loading migration is now complete for the current schema.

`arxpm` now follows the canonical `.arxproject.toml` shape provided by
`arx.settings`:

- dependencies live in `project.dependencies`
- package-manager-specific `[arxpm.*]` tables are rejected
- environment kinds are `venv`, `conda`, and `system`

Any future roadmap work around manifests should start from the shared
`arx.settings` schema first and only add `arxpm`-specific behavior when the
project intentionally reintroduces package-manager extensions.
