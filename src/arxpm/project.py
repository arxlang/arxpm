"""
title: Project lifecycle operations.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arxpm.errors import ManifestError, MissingCompilerError
from arxpm.external import CommandResult
from arxpm.manifest import (
    create_default_manifest,
    load_manifest,
    save_manifest,
)
from arxpm.models import DependencySpec, Manifest
from arxpm.pixi import PixiService

_MAIN_SOURCE = """```
title: Simple main module
```

fn main() -> i32:
  ```
  title: Print hello world
  returns:
    type: i32
  ```
  print("Hello, Arx!")
  return 0
"""

_SOURCE_SUFFIXES = (".x", ".arx")
_EXCLUDED_SOURCE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pixi",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}


class ProjectPixiAdapter(Protocol):
    """
    title: Project-level pixi adapter protocol.
    """

    def ensure_available(self) -> None:
        """
        title: Validate pixi availability.
        """

    def ensure_manifest(
        self,
        directory: Path,
        project_name: str,
        required_dependencies: tuple[str, ...],
    ) -> Path:
        """
        title: Create or sync project pixi manifest.
        parameters:
          directory:
            type: Path
          project_name:
            type: str
          required_dependencies:
            type: tuple[str, Ellipsis]
        returns:
          type: Path
        """

    def install(self, directory: Path) -> CommandResult:
        """
        title: Install pixi environment.
        parameters:
          directory:
            type: Path
        returns:
          type: CommandResult
        """

    def run(self, directory: Path, args: list[str]) -> CommandResult:
        """
        title: Run a command with pixi.
        parameters:
          directory:
            type: Path
          args:
            type: list[str]
        returns:
          type: CommandResult
        """


@dataclass(slots=True, frozen=True)
class BuildResult:
    """
    title: Build execution output.
    attributes:
      manifest:
        type: Manifest
      command_result:
        type: CommandResult
      artifact:
        type: Path
    """

    manifest: Manifest
    command_result: CommandResult
    artifact: Path


@dataclass(slots=True, frozen=True)
class RunResult:
    """
    title: Run execution output.
    attributes:
      build_result:
        type: BuildResult
      command_result:
        type: CommandResult
    """

    build_result: BuildResult
    command_result: CommandResult


@dataclass(slots=True, frozen=True)
class PublishResult:
    """
    title: Publish execution output.
    attributes:
      manifest:
        type: Manifest
      artifacts:
        type: tuple[Path, Ellipsis]
      upload_result:
        type: CommandResult | None
    """

    manifest: Manifest
    artifacts: tuple[Path, ...]
    upload_result: CommandResult | None


class ProjectService:
    """
    title: High-level project workflows.
    attributes:
      _pixi:
        type: ProjectPixiAdapter
    """

    _pixi: ProjectPixiAdapter

    def __init__(self, pixi: ProjectPixiAdapter | None = None) -> None:
        self._pixi = pixi or PixiService()

    def init(
        self,
        directory: Path,
        name: str | None = None,
        create_pixi: bool = True,
    ) -> Manifest:
        """
        title: Initialize a new Arx project.
        parameters:
          directory:
            type: Path
          name:
            type: str | None
          create_pixi:
            type: bool
        returns:
          type: Manifest
        """
        project_name = name or directory.resolve().name
        manifest_path = directory / "arxproj.toml"
        if manifest_path.exists():
            raise ManifestError("arxproj.toml already exists")

        manifest = create_default_manifest(project_name)
        save_manifest(directory, manifest)

        entry_path = directory / manifest.build.entry
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        if not entry_path.exists():
            entry_path.write_text(_MAIN_SOURCE, encoding="utf-8")

        if create_pixi:
            self._pixi.ensure_manifest(
                directory,
                manifest.project.name,
                required_dependencies=_required_pixi_dependencies(),
            )

        return manifest

    def add_dependency(
        self,
        directory: Path,
        name: str,
        path: Path | None = None,
        git: str | None = None,
    ) -> Manifest:
        """
        title: Add or update a dependency in arxproj.toml.
        parameters:
          directory:
            type: Path
          name:
            type: str
          path:
            type: Path | None
          git:
            type: str | None
        returns:
          type: Manifest
        """
        if not name.strip():
            raise ManifestError("dependency name must be a non-empty string")
        if path is not None and git is not None:
            raise ManifestError("use either --path or --git, not both")

        manifest = load_manifest(directory)

        spec: DependencySpec
        if path is not None:
            spec = DependencySpec.from_path(str(path))
        elif git is not None:
            spec = DependencySpec.from_git(git)
        else:
            spec = DependencySpec.registry()

        manifest.dependencies[name] = spec
        save_manifest(directory, manifest)
        return manifest

    def install(self, directory: Path) -> CommandResult:
        """
        title: Install or sync environment dependencies via pixi.
        parameters:
          directory:
            type: Path
        returns:
          type: CommandResult
        """
        manifest = load_manifest(directory)
        self._pixi.ensure_available()
        self._pixi.ensure_manifest(
            directory,
            manifest.project.name,
            required_dependencies=_required_pixi_dependencies(),
        )
        command_result = self._pixi.install(directory)
        self._install_manifest_dependencies(directory, manifest)
        return command_result

    def build(self, directory: Path) -> BuildResult:
        """
        title: Build a project by calling arx through pixi.
        parameters:
          directory:
            type: Path
        returns:
          type: BuildResult
        """
        manifest = load_manifest(directory)
        self._pixi.ensure_available()

        compiler = manifest.toolchain.compiler.strip()
        if not compiler:
            raise MissingCompilerError("toolchain.compiler cannot be empty")

        entry_path = directory / manifest.build.entry
        if not entry_path.exists():
            raise ManifestError(f"build entry does not exist: {entry_path}")

        artifact_rel = Path(manifest.build.out_dir) / manifest.project.name
        artifact_path = directory / artifact_rel
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            compiler,
            manifest.build.entry,
            "--output-file",
            str(artifact_rel),
        ]
        command_result = self._pixi.run(directory, command)

        return BuildResult(
            manifest=manifest,
            command_result=command_result,
            artifact=artifact_path,
        )

    def run(self, directory: Path) -> RunResult:
        """
        title: Build and run the produced artifact through pixi.
        parameters:
          directory:
            type: Path
        returns:
          type: RunResult
        """
        build_result = self.build(directory)
        artifact_rel = Path(build_result.manifest.build.out_dir)
        artifact_rel = artifact_rel / build_result.manifest.project.name
        command_result = self._pixi.run(directory, [str(artifact_rel)])
        return RunResult(
            build_result=build_result,
            command_result=command_result,
        )

    def pack(self, directory: Path) -> PublishResult:
        """
        title: Build package artifacts without uploading.
        parameters:
          directory:
            type: Path
        returns:
          type: PublishResult
        """
        return self.publish(directory, dry_run=True)

    def publish(
        self,
        directory: Path,
        repository_url: str | None = None,
        skip_existing: bool = False,
        dry_run: bool = False,
    ) -> PublishResult:
        """
        title: Build and publish project sources as a Python package.
        parameters:
          directory:
            type: Path
          repository_url:
            type: str | None
          skip_existing:
            type: bool
          dry_run:
            type: bool
        returns:
          type: PublishResult
        """
        manifest = load_manifest(directory)
        self._pixi.ensure_available()
        self._pixi.ensure_manifest(
            directory,
            manifest.project.name,
            required_dependencies=_required_pixi_dependencies(),
        )
        self._pixi.install(directory)

        if repository_url is not None and not repository_url.strip():
            raise ManifestError("repository URL cannot be empty")

        # Ensure build/upload tooling is present in the active pixi env.
        self._pixi.run(
            directory,
            [
                "python",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--quiet",
                "build",
                "twine",
            ],
        )

        dist_dir = directory / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        artifacts_before = {
            path.resolve() for path in dist_dir.iterdir() if path.is_file()
        }

        with tempfile.TemporaryDirectory(prefix="arxpm-publish-") as temp_dir:
            staging_dir = Path(temp_dir) / "package"
            _prepare_publish_workspace(directory, manifest, staging_dir)
            self._pixi.run(
                directory,
                [
                    "python",
                    "-m",
                    "build",
                    "--sdist",
                    "--wheel",
                    "--outdir",
                    str(dist_dir),
                    str(staging_dir),
                ],
            )

        artifacts = tuple(
            sorted(
                (
                    path
                    for path in dist_dir.iterdir()
                    if path.is_file()
                    and path.resolve() not in artifacts_before
                ),
                key=lambda path: path.name,
            )
        )
        if not artifacts:
            raise ManifestError("publish build produced no artifacts")

        if dry_run:
            return PublishResult(
                manifest=manifest,
                artifacts=artifacts,
                upload_result=None,
            )

        upload_cmd = [
            "python",
            "-m",
            "twine",
            "upload",
            "--non-interactive",
        ]
        if repository_url:
            upload_cmd.extend(["--repository-url", repository_url.strip()])
        if skip_existing:
            upload_cmd.append("--skip-existing")
        upload_cmd.extend(str(path) for path in artifacts)

        upload_result = self._pixi.run(directory, upload_cmd)
        return PublishResult(
            manifest=manifest,
            artifacts=artifacts,
            upload_result=upload_result,
        )

    def _install_manifest_dependencies(
        self,
        directory: Path,
        manifest: Manifest,
    ) -> None:
        for dependency_name, spec in sorted(manifest.dependencies.items()):
            target = _dependency_install_target(dependency_name, spec)
            self._pixi.run(
                directory,
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    target,
                ],
            )


def _required_pixi_dependencies() -> tuple[str, ...]:
    return ("clang", "python")


def _dependency_install_target(name: str, spec: DependencySpec) -> str:
    if spec.source is not None:
        return name
    if spec.path is not None:
        return spec.path
    if spec.git is not None:
        if spec.git.startswith("git+"):
            return spec.git
        return f"git+{spec.git}"
    raise ManifestError(f"dependency {name!r} has no installable target")


def _prepare_publish_workspace(
    directory: Path,
    manifest: Manifest,
    staging_dir: Path,
) -> None:
    package_name = _distribution_to_package_name(manifest.project.name)
    package_root = staging_dir / "src" / package_name
    package_root.mkdir(parents=True, exist_ok=True)

    source_paths = _discover_arx_sources(directory)
    if not source_paths:
        raise ManifestError(
            "no Arx source files found to publish (expected .x or .arx)"
        )

    for relative_source in source_paths:
        source_path = directory / relative_source
        target_path = package_root / relative_source
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    manifest_path = directory / "arxproj.toml"
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")

    shutil.copy2(manifest_path, package_root / "arxproj.toml")
    (package_root / "__init__.py").write_text(
        _render_package_init(manifest),
        encoding="utf-8",
    )

    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "pyproject.toml").write_text(
        _render_publish_pyproject(manifest, package_name),
        encoding="utf-8",
    )
    (staging_dir / "README.md").write_text(
        _render_publish_readme(manifest),
        encoding="utf-8",
    )


def _discover_arx_sources(directory: Path) -> list[Path]:
    sources: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix not in _SOURCE_SUFFIXES:
            continue

        relative = path.relative_to(directory)
        if any(part in _EXCLUDED_SOURCE_DIRS for part in relative.parts):
            continue
        sources.append(relative)

    return sorted(sources)


def _distribution_to_package_name(project_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_")
    if not cleaned:
        raise ManifestError("project.name must contain letters or numbers")

    if cleaned[0].isdigit():
        cleaned = f"pkg_{cleaned}"
    return f"arxpkg_{cleaned.lower()}"


def _render_package_init(manifest: Manifest) -> str:
    name = _toml_quote(manifest.project.name)
    version = _toml_quote(manifest.project.version)
    return (
        "\n".join(
            [
                '"""Generated Arx package metadata."""',
                "",
                f"PROJECT_NAME = {name}",
                f"PROJECT_VERSION = {version}",
                "",
                '__all__ = ["PROJECT_NAME", "PROJECT_VERSION"]',
            ]
        )
        + "\n"
    )


def _render_publish_pyproject(
    manifest: Manifest,
    package_name: str,
) -> str:
    description = f"Published Arx package for project {manifest.project.name}."
    lines = [
        "[build-system]",
        'requires = ["hatchling>=1.25.0"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        f"name = {_toml_quote(manifest.project.name)}",
        f"version = {_toml_quote(manifest.project.version)}",
        f"description = {_toml_quote(description)}",
        'readme = "README.md"',
        'requires-python = ">=3.10"',
        "",
        "[tool.hatch.build.targets.wheel]",
        f'packages = ["src/{package_name}"]',
        "include = [",
        f'  "src/{package_name}/**/*.x",',
        f'  "src/{package_name}/**/*.arx",',
        f'  "src/{package_name}/arxproj.toml",',
        "]",
        "",
        "[tool.hatch.build.targets.sdist]",
        "include = [",
        f'  "src/{package_name}/**/*",',
        '  "README.md",',
        '  "pyproject.toml",',
        "]",
    ]
    return "\n".join(lines) + "\n"


def _render_publish_readme(manifest: Manifest) -> str:
    return (
        "\n".join(
            [
                f"# {manifest.project.name}",
                "",
                "This package was generated by arxpm publish.",
                "",
                "It includes:",
                "",
                "- arxproj.toml",
                "- Arx source files (*.x, *.arx)",
            ]
        )
        + "\n"
    )


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)
