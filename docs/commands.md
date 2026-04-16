# Commands

## `arxpm init`

Create a new project in the target directory.

```bash
arxpm init --name hello-arx
arxpm init --directory ./my-project --no-pixi
```

Effects:

- creates `.arxproject.toml`
- creates `src/main.x`
- optionally creates/updates `pixi.toml`

## `arxpm add`

Add a dependency entry to `.arxproject.toml`.

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

## `arxpm compile`

Compile through Pixi using the configured compiler. This is a clearer alias for
`arxpm build` (which is kept for compatibility).

```bash
arxpm compile
arxpm compile --directory examples
```

## `arxpm run`

Build and then run the produced artifact through Pixi.

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
`.arxproject.toml` and `*.x`/`*.arx` sources.

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
