# Commands

## `arxpm init`

Create a new project in the target directory.

```bash
arxpm init --name hello-arx
arxpm init --directory ./my-project --no-pixi
```

Effects:

- creates `arxproj.toml`
- creates `src/main.x`
- optionally creates/updates `pixi.toml`

## `arxpm add`

Add a dependency entry to `arxproj.toml`.

```bash
arxpm add http
arxpm add mylib --path ../mylib
arxpm add utils --git https://example.com/utils.git
```

## `arxpm install`

Validate project metadata, ensure Pixi sync, and run install.

```bash
arxpm install
arxpm install --directory examples
```

Dependency entries are installed with pip inside the project pixi env:

- registry: `pip install <name>`
- path: `pip install <path>`
- git: `pip install git+<url>`

## `arxpm build`

Compile through Pixi using the configured compiler.

```bash
arxpm build
arxpm build --directory examples
```

Current Arx invocation uses:

```text
arx <entry> --output-file <out_dir>/<project_name>
```

## `arxpm run`

Build and then run the produced artifact through Pixi.

```bash
arxpm run
arxpm run --directory examples
```

Build/compiler output and the application stdout/stderr are streamed directly;
`arxpm run` does not print an extra completion line.

## `arxpm publish`

Build and publish the current project as a Python package that bundles
`arxproj.toml` and `*.x`/`*.arx` sources.

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<pypi-token>
arxpm publish
arxpm publish --repository-url https://test.pypi.org/legacy/
arxpm publish --dry-run
```

## `arxpm doctor`

Report environment health and manifest status.

```bash
arxpm doctor
```
