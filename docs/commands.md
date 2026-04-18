# Commands

## `arxpm init`

Create a new project in the target directory.

```bash
arxpm init --name hello-arx
arxpm init --directory ./my-project
arxpm init --env-kind existing-venv --env-path ./shared-venv
arxpm init --env-kind conda --env-name myproject-env
```

Effects:

- creates `.arxproject.toml`
- creates `src/main.x`
- writes an explicit `[environment]` block only when `--env-kind`, `--env-path`,
  or `--env-name` is provided

See [Environments](environments.md) for the supported strategies.

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
arxpm install --dev
```

Dependency entries are installed as follows:

- registry: `uv pip install <name>`
- path: `uv pip install <path>` (non-Arx paths) or pack+install+symlink flow
  (Arx libraries with an `.arxproject.toml`)
- git: `uv pip install git+<url>`

## `arxpm build`

Invoke the configured Arx compiler directly.

```bash
arxpm build
arxpm build --directory examples
```

Current Arx invocation uses:

```text
arx <entry> --output-file <out_dir>/<project_name>
```

## `arxpm compile`

Alias for `arxpm build`. Clearer name for anyone treating `build` as a packaging
operation.

```bash
arxpm compile
arxpm compile --directory examples
```

## `arxpm run`

Build and then run the produced artifact.

```bash
arxpm run
arxpm run --directory examples
```

The command shows compiler and program output directly in your terminal.

## `arxpm pack`

Build package artifacts locally without uploading to a registry.

```bash
arxpm pack
arxpm pack --directory examples
```

## `arxpm publish`

Build and publish the current project as a Python package that bundles
`.arxproject.toml` and `*.x`/`*.arx` sources. Build and upload tools (`build`,
`twine`) run from the outer interpreter that is executing `arxpm`; they are
never installed into your project environment.

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<pypi-token>
arxpm publish
arxpm publish --repository-url https://test.pypi.org/legacy/
arxpm publish --dry-run
```

## `arxpm healthcheck`

Report environment health and manifest status.

```bash
arxpm healthcheck
```

Checks:

- `.arxproject.toml` exists and parses
- `uv` is on PATH
- the configured compiler (`toolchain.compiler`) is on PATH
- the declared environment is reachable
