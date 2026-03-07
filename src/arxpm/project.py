"""Project lifecycle operations."""

from __future__ import annotations

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

_MAIN_SOURCE = 'fn main() {\n    print("Hello, Arx!");\n}\n'


class ProjectPixiAdapter(Protocol):
    """Project-level pixi adapter protocol."""

    def ensure_available(self) -> None:
        """Validate pixi availability."""

    def ensure_manifest(
        self,
        directory: Path,
        project_name: str,
        required_dependencies: tuple[str, ...],
    ) -> Path:
        """Create or sync project pixi manifest."""

    def install(self, directory: Path) -> CommandResult:
        """Install pixi environment."""

    def run(self, directory: Path, args: list[str]) -> CommandResult:
        """Run a command with pixi."""


@dataclass(slots=True, frozen=True)
class BuildResult:
    """Build execution output."""

    manifest: Manifest
    command_result: CommandResult
    artifact: Path


@dataclass(slots=True, frozen=True)
class RunResult:
    """Run execution output."""

    build_result: BuildResult
    command_result: CommandResult


class ProjectService:
    """High-level project workflows."""

    def __init__(self, pixi: ProjectPixiAdapter | None = None) -> None:
        self._pixi = pixi or PixiService()

    def init(
        self,
        directory: Path,
        name: str | None = None,
        create_pixi: bool = True,
    ) -> Manifest:
        """Initialize a new Arx project."""
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
        """Add or update a dependency in arxproj.toml."""
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
        """Install or sync environment dependencies via pixi."""
        manifest = load_manifest(directory)
        self._pixi.ensure_available()
        self._pixi.ensure_manifest(
            directory,
            manifest.project.name,
            required_dependencies=_required_pixi_dependencies(),
        )
        return self._pixi.install(directory)

    def build(self, directory: Path) -> BuildResult:
        """Build a project by calling arx through pixi."""
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

        command = [compiler, manifest.build.entry, "-o", str(artifact_rel)]
        command_result = self._pixi.run(directory, command)

        return BuildResult(
            manifest=manifest,
            command_result=command_result,
            artifact=artifact_path,
        )

    def run(self, directory: Path) -> RunResult:
        """Build and run the produced artifact through pixi."""
        build_result = self.build(directory)
        artifact_rel = Path(build_result.manifest.build.out_dir)
        artifact_rel = artifact_rel / build_result.manifest.project.name
        command_result = self._pixi.run(directory, [str(artifact_rel)])
        return RunResult(
            build_result=build_result,
            command_result=command_result,
        )


def _required_pixi_dependencies() -> tuple[str, ...]:
    return ("clang", "python")
