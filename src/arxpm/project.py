"""
title: Project lifecycle operations.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from arxpm.environment import (
    EnvironmentFactory,
    EnvironmentRuntime,
    build_environment,
)
from arxpm.errors import ManifestError, MissingCompilerError
from arxpm.external import CommandResult, CommandRunner, run_command
from arxpm.manifest import (
    MANIFEST_FILENAME,
    create_default_manifest,
    load_manifest,
    save_manifest,
)
from arxpm.models import DependencySpec, EnvironmentConfig, Manifest

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
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}


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
      _environment_factory:
        type: EnvironmentFactory
      _runner:
        type: CommandRunner
    """

    _environment_factory: EnvironmentFactory
    _runner: CommandRunner

    def __init__(
        self,
        environment_factory: EnvironmentFactory | None = None,
        runner: CommandRunner = run_command,
    ) -> None:
        self._environment_factory = environment_factory or build_environment
        self._runner = runner

    def init(
        self,
        directory: Path,
        name: str | None = None,
        environment: EnvironmentConfig | None = None,
    ) -> Manifest:
        """
        title: Initialize a new Arx project.
        parameters:
          directory:
            type: Path
          name:
            type: str | None
          environment:
            type: EnvironmentConfig | None
        returns:
          type: Manifest
        """
        project_name = name or directory.resolve().name
        manifest_path = directory / MANIFEST_FILENAME
        if manifest_path.exists():
            manifest = load_manifest(directory)
        else:
            manifest = create_default_manifest(project_name)
            if environment is not None:
                manifest.environment = environment
            save_manifest(directory, manifest)

        entry_path = directory / manifest.build.source_path
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        if not entry_path.exists():
            entry_path.write_text(_MAIN_SOURCE, encoding="utf-8")

        return manifest

    def add_dependency(
        self,
        directory: Path,
        name: str,
        path: Path | None = None,
        git: str | None = None,
    ) -> Manifest:
        """
        title: Add or update a dependency in .arxproject.toml.
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

    def install(
        self,
        directory: Path,
        dev: bool = False,
    ) -> CommandResult:
        """
        title: Install or sync environment dependencies.
        parameters:
          directory:
            type: Path
          dev:
            type: bool
        returns:
          type: CommandResult
        """
        manifest = load_manifest(directory)
        environment = self._environment_factory(manifest, directory)
        environment.ensure_ready()

        registry_reqs, path_deps = _partition_dependencies(
            directory,
            manifest.dependencies,
        )
        command_result = environment.install_packages(registry_reqs)
        for dependency_name, library_directory in path_deps:
            self._install_arx_path_dependency(
                directory,
                environment,
                dependency_name,
                library_directory,
            )

        if dev:
            dev_registry, dev_paths = _partition_dependencies(
                directory,
                manifest.dev_dependencies,
            )
            environment.install_packages(dev_registry)
            for dependency_name, library_directory in dev_paths:
                self._install_arx_path_dependency(
                    directory,
                    environment,
                    dependency_name,
                    library_directory,
                )

        return command_result

    def build(self, directory: Path) -> BuildResult:
        """
        title: Build a project by invoking the configured Arx compiler.
        parameters:
          directory:
            type: Path
        returns:
          type: BuildResult
        """
        manifest = load_manifest(directory)

        compiler = manifest.toolchain.compiler.strip()
        if not compiler:
            raise MissingCompilerError("toolchain.compiler cannot be empty")

        source_path = manifest.build.source_path
        entry_path = directory / source_path
        if not entry_path.exists():
            raise ManifestError(f"build entry does not exist: {entry_path}")

        artifact_rel = Path(manifest.build.out_dir) / manifest.project.name
        artifact_path = directory / artifact_rel
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            compiler,
            source_path,
            "--output-file",
            str(artifact_rel),
        ]
        command_result = self._runner(command, cwd=directory, check=True)

        return BuildResult(
            manifest=manifest,
            command_result=command_result,
            artifact=artifact_path,
        )

    def run(self, directory: Path) -> RunResult:
        """
        title: Build and run the produced artifact.
        parameters:
          directory:
            type: Path
        returns:
          type: RunResult
        """
        build_result = self.build(directory)
        artifact_rel = Path(build_result.manifest.build.out_dir)
        artifact_rel = artifact_rel / build_result.manifest.project.name
        command_result = self._runner(
            [str(artifact_rel)],
            cwd=directory,
            check=True,
        )
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

        if repository_url is not None and not repository_url.strip():
            raise ManifestError("repository URL cannot be empty")

        dist_dir = directory / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        artifacts_before = {
            path.resolve() for path in dist_dir.iterdir() if path.is_file()
        }

        with tempfile.TemporaryDirectory(prefix="arxpm-publish-") as temp_dir:
            staging_dir = Path(temp_dir) / "package"
            _prepare_publish_workspace(directory, manifest, staging_dir)
            self._runner(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--sdist",
                    "--wheel",
                    "--outdir",
                    str(dist_dir),
                    str(staging_dir),
                ],
                cwd=directory,
                check=True,
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
            sys.executable,
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

        upload_result = self._runner(upload_cmd, cwd=directory, check=True)
        return PublishResult(
            manifest=manifest,
            artifacts=artifacts,
            upload_result=upload_result,
        )

    def _install_arx_path_dependency(
        self,
        directory: Path,
        environment: EnvironmentRuntime,
        dependency_name: str,
        library_directory: Path,
    ) -> None:
        """
        title: Pack, install, and symlink an Arx path dependency.
        parameters:
          directory:
            type: Path
          environment:
            type: EnvironmentRuntime
          dependency_name:
            type: str
          library_directory:
            type: Path
        """
        library_manifest = load_manifest(library_directory)
        module_name = _arx_module_name(library_manifest.project.name)
        if module_name != dependency_name:
            raise ManifestError(
                f"dependency {dependency_name!r} must match the library's "
                f"Arx module name {module_name!r} "
                f"(derived from project.name = "
                f"{library_manifest.project.name!r})"
            )

        pack_result = self.pack(library_directory)
        wheels = [
            artifact
            for artifact in pack_result.artifacts
            if artifact.suffix == ".whl"
        ]
        if not wheels:
            raise ManifestError(
                f"packing {library_directory} produced no wheel artifact"
            )
        wheel = wheels[0]

        environment.install_packages(
            [str(wheel)],
            force_reinstall=True,
            no_deps=True,
        )

        probe = self._runner(
            [
                str(environment.python_executable()),
                "-c",
                (
                    f"import {module_name}, os; "
                    f"print(os.path.dirname({module_name}.__file__))"
                ),
            ],
            cwd=directory,
            check=True,
        )
        install_dir = Path(probe.stdout.strip().splitlines()[-1])
        if not install_dir.is_dir():
            raise ManifestError(
                f"installed {module_name!r} directory not found: {install_dir}"
            )

        link_path = directory / module_name
        if link_path.is_symlink() or link_path.exists():
            if link_path.is_symlink() or link_path.is_file():
                link_path.unlink()
            else:
                shutil.rmtree(link_path)
        link_path.symlink_to(install_dir, target_is_directory=True)


def _partition_dependencies(
    directory: Path,
    dependencies: dict[str, DependencySpec],
) -> tuple[list[str], list[tuple[str, Path]]]:
    registry_reqs: list[str] = []
    path_deps: list[tuple[str, Path]] = []
    for dependency_name, spec in sorted(dependencies.items()):
        if spec.path is not None:
            library_directory = (directory / spec.path).resolve()
            if _is_arx_project(library_directory):
                path_deps.append((dependency_name, library_directory))
                continue
        registry_reqs.append(_dependency_install_target(dependency_name, spec))
    return registry_reqs, path_deps


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
    package_name = _arx_module_name(manifest.project.name)
    package_root = staging_dir / "src" / package_name
    package_root.mkdir(parents=True, exist_ok=True)

    source_paths = _discover_arx_sources(directory)
    if not source_paths:
        raise ManifestError(
            "no Arx source files found to publish (expected .x or .arx)"
        )

    source_root = Path(manifest.build.src_dir)
    for relative_source in source_paths:
        source_path = directory / relative_source
        bundled_rel = _bundled_source_path(relative_source, source_root)
        target_path = package_root / bundled_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    manifest_path = directory / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")

    shutil.copy2(manifest_path, package_root / MANIFEST_FILENAME)
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


def _bundled_source_path(relative_source: Path, source_root: Path) -> Path:
    """
    title: Drop the source root prefix so bundled files land at package root.
    parameters:
      relative_source:
        type: Path
      source_root:
        type: Path
    returns:
      type: Path
    """
    if source_root == Path("") or source_root == Path("."):
        return relative_source
    try:
        return relative_source.relative_to(source_root)
    except ValueError:
        return relative_source


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


def _is_arx_project(path: Path) -> bool:
    return path.is_dir() and (path / MANIFEST_FILENAME).is_file()


def _arx_module_name(project_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_")
    if not cleaned:
        raise ManifestError("project.name must contain letters or numbers")

    if cleaned[0].isdigit():
        cleaned = f"pkg_{cleaned}"
    return cleaned.lower()


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
        f'  "src/{package_name}/.arxproject.toml",',
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
                "- .arxproject.toml",
                "- Arx source files (*.x, *.arx)",
            ]
        )
        + "\n"
    )


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)
