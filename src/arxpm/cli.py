"""
title: Typer CLI for arxpm.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from arxpm.doctor import DoctorService
from arxpm.errors import ArxpmError
from arxpm.project import ProjectService

app = typer.Typer(help="Arx project and package manager.")


def _fail(error: Exception) -> NoReturn:
    typer.secho(f"error: {error}", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


def _resolve(directory: Path) -> Path:
    return directory.resolve()


@app.command()
def init(
    name: Annotated[
        str | None,
        typer.Option("--name", help="Project name override."),
    ] = None,
    pixi: Annotated[
        bool,
        typer.Option("--pixi/--no-pixi", help="Create or update pixi.toml."),
    ] = True,
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Initialize a new Arx project.
    parameters:
      name:
        type: >-
          Annotated[str | None, typer.Option('--name', help='Project name
          override.')]
      pixi:
        type: >-
          Annotated[bool, typer.Option('--pixi/--no-pixi', help='Create or
          update pixi.toml.')]
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    target = _resolve(directory)
    try:
        manifest = project_service.init(target, name=name, create_pixi=pixi)
    except ArxpmError as exc:
        _fail(exc)

    typer.echo(f"Initialized project {manifest.project.name} at {target}")
    if pixi:
        typer.echo("Ensured pixi.toml.")


@app.command()
def install(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Install project environment with pixi.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    try:
        project_service.install(_resolve(directory))
    except ArxpmError as exc:
        _fail(exc)

    typer.echo("Environment synchronized with pixi.")


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Dependency name.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Local path dependency."),
    ] = None,
    git: Annotated[
        str | None,
        typer.Option("--git", help="Git URL dependency."),
    ] = None,
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Add a dependency entry to .arxproject.toml.
    parameters:
      name:
        type: Annotated[str, typer.Argument(help='Dependency name.')]
      path:
        type: >-
          Annotated[Path | None, typer.Option('--path', help='Local path
          dependency.')]
      git:
        type: >-
          Annotated[str | None, typer.Option('--git', help='Git URL
          dependency.')]
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    try:
        manifest = project_service.add_dependency(
            _resolve(directory),
            name=name,
            path=path,
            git=git,
        )
    except ArxpmError as exc:
        _fail(exc)

    kind = manifest.dependencies[name].kind
    typer.echo(f"Added dependency {name} ({kind}).")


def _compile_project(directory: Path, label: str) -> None:
    project_service = ProjectService()
    try:
        result = project_service.build(_resolve(directory))
    except ArxpmError as exc:
        _fail(exc)

    typer.echo(f"{label} completed. Artifact target: {result.artifact}")


@app.command("build")
def build_command(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Build project using arx through pixi.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    _compile_project(directory, "Build")


@app.command("compile")
def compile_command(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Compile project sources into a runnable binary artifact.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    _compile_project(directory, "Compile")


@app.command("run")
def run_command(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Build and run project artifact.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    try:
        project_service.run(_resolve(directory))
    except ArxpmError as exc:
        _fail(exc)


@app.command("pack")
def pack_command(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Build package artifacts without uploading to an index.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    try:
        result = project_service.pack(_resolve(directory))
    except ArxpmError as exc:
        _fail(exc)

    artifacts = ", ".join(str(path) for path in result.artifacts)
    typer.echo(f"Pack completed. Artifacts: {artifacts}")


@app.command("publish")
def publish_command(
    repository_url: Annotated[
        str | None,
        typer.Option(
            "--repository-url",
            help="Override Python package repository upload URL.",
        ),
    ] = None,
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--no-skip-existing",
            help="Skip artifacts that already exist remotely.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Build publish artifacts without uploading.",
        ),
    ] = False,
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Build and publish package artifacts to a PyPI-compatible index.
    parameters:
      repository_url:
        type: >-
          Annotated[str | None, typer.Option('--repository-url', help='Override
          Python package repository upload URL.')]
      skip_existing:
        type: >-
          Annotated[bool, typer.Option('--skip-existing/--no-skip-existing',
          help='Skip artifacts that already exist remotely.')]
      dry_run:
        type: >-
          Annotated[bool, typer.Option('--dry-run', help='Build publish
          artifacts without uploading.')]
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    project_service = ProjectService()
    try:
        result = project_service.publish(
            _resolve(directory),
            repository_url=repository_url,
            skip_existing=skip_existing,
            dry_run=dry_run,
        )
    except ArxpmError as exc:
        _fail(exc)

    artifacts = ", ".join(str(path) for path in result.artifacts)
    if dry_run:
        typer.echo(f"Publish dry-run completed. Artifacts: {artifacts}")
        return

    typer.echo(f"Published artifacts: {artifacts}")


@app.command()
def doctor(
    directory: Annotated[
        Path,
        typer.Option("--directory", "-C", help="Project directory."),
    ] = Path("."),
) -> None:
    """
    title: Report environment and project health.
    parameters:
      directory:
        type: >-
          Annotated[Path, typer.Option('--directory', '-C', help='Project
          directory.')]
    """
    doctor_service = DoctorService()
    report = doctor_service.run(_resolve(directory))

    for check in report.checks:
        status = "ok" if check.ok else "fail"
        typer.echo(f"[{status}] {check.name}: {check.message}")

    if not report.ok:
        raise typer.Exit(code=1)
