# Contributing

Contributions are welcome.

## Setup

```bash
git clone https://github.com/arxlang/arxpm.git
cd arxpm
mamba env create --file conda/dev.yaml
conda activate arxpm
poetry config virtualenvs.create false
poetry install --with dev
```

## Local Checks

```bash
makim tests.unit
makim tests.smoke
makim tests.linter
makim docs.build
```

`makim tests.smoke` installs and builds every example, but only runs examples
whose resolved `build.mode` is `"app"`. Library examples are expected to stop
after a successful build.

## Pull Requests

- keep changes focused
- include tests for behavior changes
- update docs when user-facing behavior changes
- keep Python 3.10+ compatibility

## Release Model

This repository uses semantic-release. Follow conventional commit style in PR
titles/messages.
