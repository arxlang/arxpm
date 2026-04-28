# Commands

## `arxpm init`

Create a new app project in the target directory.

```bash
arxpm init --name hello-arx
arxpm init --directory ./my-project
arxpm init --env-kind venv --env-path ./shared-venv
arxpm init --env-kind conda --env-name myproject-env
arxpm init --env-kind system
```

Effects:

- creates `.arxproject.toml`
- creates `src/<package>/__init__.x`
- creates `src/<package>/main.x`
- writes `build.mode = "app"`
- writes `build.package` when `project.name` is not a valid package identifier
- writes an explicit `[environment]` block only when `--env-kind`, `--env-path`,
  or `--env-name` is provided

## `arxpm config`

Configure user-level arxpm settings. Publish tokens are stored in the system
keyring only; arxpm does not write tokens to project files or plaintext config
files.

```bash
arxpm config pypi-token.pypi
arxpm config pypi-token.testpypi
arxpm config --unset pypi-token.pypi
```

The token value is entered through a hidden prompt. If no supported keyring is
available, use `ARXPM_PUBLISH_TOKEN` for a single publish or configure a keyring
backend.

## `arxpm add`

Add a dependency entry to `.arxproject.toml`.

```bash
arxpm add http
arxpm add mylib --path ../mylib
arxpm add utils --git https://example.com/utils.git
```

## `arxpm install`

Validate project metadata, prepare the configured Python environment, and
install dependencies with `uv`.

```bash
arxpm install
arxpm install --directory examples
arxpm install --group dev
```

## `arxpm build`

Resolve the effective layout, validate it, choose the default target file, and
invoke the configured Arx compiler directly.

```bash
arxpm build
arxpm build --directory examples
```

Arx invocation uses one of these targets:

- app: `arx <src_dir>/<package>/main.x --output-file <out_dir>/<package>`
- lib: `arx <src_dir>/<package>/__init__.x --output-file <out_dir>/<package>`

## `arxpm compile`

Alias for `arxpm build`.

## `arxpm run`

Build and then run the produced artifact.

```bash
arxpm run
arxpm run --directory examples
```

`arxpm run` is only valid for app projects.

## `arxpm pack`

Build package artifacts locally without uploading to a registry. The command
produces both a source distribution (`.tar.gz`) and a wheel (`.whl`) so source
files remain available for debugging and import resolution.

## `arxpm publish`

Build and publish the current project as a Python package that bundles
`.arxproject.toml` and `*.x`/`*.arx` sources in both source distribution and
wheel artifacts. The generated package metadata also includes
`project.dependencies`, so Python installers can resolve transitive package
dependencies.

The default repository is the official PyPI upload endpoint:
`https://upload.pypi.org/legacy/`. Override it with `--repository-url` or
`ARXPM_PUBLISH_REPOSITORY_URL`.

Use `ARXPM_PUBLISH_TOKEN` for PyPI or TestPyPI API tokens:

```bash
ARXPM_PUBLISH_TOKEN="pypi-..." arxpm publish
ARXPM_PUBLISH_REPOSITORY_URL="https://test.pypi.org/legacy/" \
  ARXPM_PUBLISH_TOKEN="pypi-..." arxpm publish
```

To store a token safely for repeated local publishes, use:

```bash
arxpm config pypi-token.pypi
arxpm config pypi-token.testpypi
```

`pypi-token.pypi` is used for the default PyPI upload URL. `pypi-token.testpypi`
is used when publishing to `https://test.pypi.org/legacy/`.

For repositories that use basic authentication, set `ARXPM_PUBLISH_USERNAME` and
`ARXPM_PUBLISH_PASSWORD`.

## `arxpm healthcheck`

Report manifest, layout, environment, and toolchain health.

```bash
arxpm healthcheck
```

## `arxpm doctor`

Alias for `arxpm healthcheck` with the same checks and exit behavior.

```bash
arxpm doctor
```
