"""
title: Typed data models for Arx project manifests.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from arxpm.errors import ManifestError


@dataclass(slots=True, frozen=True)
class ProjectConfig:
    """
    title: Project metadata.
    attributes:
      name:
        type: str
      version:
        type: str
      edition:
        type: str
    """

    name: str
    version: str = "0.1.0"
    edition: str = "2026"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ManifestError("project.name must be a non-empty string")
        if not self.version.strip():
            raise ManifestError("project.version must be a non-empty string")
        if not self.edition.strip():
            raise ManifestError("project.edition must be a non-empty string")


@dataclass(slots=True, frozen=True)
class BuildConfig:
    """
    title: Build configuration.
    attributes:
      entry:
        type: str
      out_dir:
        type: str
    """

    entry: str = "src/main.arx"
    out_dir: str = "build"

    def __post_init__(self) -> None:
        if not self.entry.strip():
            raise ManifestError("build.entry must be a non-empty string")
        if not self.out_dir.strip():
            raise ManifestError("build.out_dir must be a non-empty string")


@dataclass(slots=True, frozen=True)
class ToolchainConfig:
    """
    title: Toolchain configuration.
    attributes:
      compiler:
        type: str
      linker:
        type: str
    """

    compiler: str = "arx"
    linker: str = "clang"

    def __post_init__(self) -> None:
        if not self.compiler.strip():
            raise ManifestError(
                "toolchain.compiler must be a non-empty string"
            )
        if not self.linker.strip():
            raise ManifestError("toolchain.linker must be a non-empty string")


@dataclass(slots=True, frozen=True)
class DependencySpec:
    """
    title: Dependency source specification.
    attributes:
      source:
        type: str | None
      path:
        type: str | None
      git:
        type: str | None
    """

    source: str | None = None
    path: str | None = None
    git: str | None = None

    def __post_init__(self) -> None:
        forms = int(self.source is not None)
        forms += int(self.path is not None)
        forms += int(self.git is not None)
        if forms != 1:
            raise ManifestError(
                "dependency must define exactly one of source, path, or git"
            )
        if self.source is not None and self.source != "registry":
            raise ManifestError("dependency source must be 'registry' in v0")
        if self.path is not None and not self.path.strip():
            raise ManifestError("dependency path must be non-empty")
        if self.git is not None and not self.git.strip():
            raise ManifestError("dependency git must be non-empty")

    @property
    def kind(self) -> str:
        """
        title: Return dependency kind.
        returns:
          type: str
        """
        if self.source is not None:
            return "registry"
        if self.path is not None:
            return "path"
        return "git"

    @classmethod
    def registry(cls) -> DependencySpec:
        """
        title: Create a registry placeholder dependency.
        returns:
          type: DependencySpec
        """
        return cls(source="registry")

    @classmethod
    def from_path(cls, path: str) -> DependencySpec:
        """
        title: Create a local path dependency.
        parameters:
          path:
            type: str
        returns:
          type: DependencySpec
        """
        return cls(path=path)

    @classmethod
    def from_git(cls, git: str) -> DependencySpec:
        """
        title: Create a git dependency.
        parameters:
          git:
            type: str
        returns:
          type: DependencySpec
        """
        return cls(git=git)

    @classmethod
    def from_value(cls, name: str, value: Any) -> DependencySpec:
        """
        title: Parse a dependency from TOML value.
        parameters:
          name:
            type: str
          value:
            type: Any
        returns:
          type: DependencySpec
        """
        if not isinstance(value, Mapping):
            raise ManifestError(f"dependency {name!r} must be a table")

        allowed = {"source", "path", "git"}
        unknown = [key for key in value if key not in allowed]
        if unknown:
            keys = ", ".join(sorted(unknown))
            raise ManifestError(
                f"dependency {name!r} has unsupported keys: {keys}"
            )

        if "source" in value:
            source = _require_string(value, "source", f"dependency {name!r}")
            if source != "registry":
                raise ManifestError(
                    f"dependency {name!r} source must be 'registry' in v0"
                )
            return cls.registry()

        if "path" in value:
            path = _require_string(value, "path", f"dependency {name!r}")
            return cls.from_path(path)

        if "git" in value:
            git = _require_string(value, "git", f"dependency {name!r}")
            return cls.from_git(git)

        raise ManifestError(
            f"dependency {name!r} must define one of source, path, or git"
        )

    def to_dict(self) -> dict[str, str]:
        """
        title: Serialize dependency spec to TOML-compatible mapping.
        returns:
          type: dict[str, str]
        """
        if self.source is not None:
            return {"source": self.source}
        if self.path is not None:
            return {"path": self.path}
        if self.git is not None:
            return {"git": self.git}
        raise ManifestError("invalid dependency state")


@dataclass(slots=True)
class Manifest:
    """
    title: Arx project manifest model.
    attributes:
      project:
        type: ProjectConfig
      build:
        type: BuildConfig
      dependencies:
        type: dict[str, DependencySpec]
      toolchain:
        type: ToolchainConfig
    """

    project: ProjectConfig
    build: BuildConfig = field(default_factory=BuildConfig)
    dependencies: dict[str, DependencySpec] = field(default_factory=dict)
    toolchain: ToolchainConfig = field(default_factory=ToolchainConfig)

    @classmethod
    def default(cls, project_name: str) -> Manifest:
        """
        title: Create a default project manifest.
        parameters:
          project_name:
            type: str
        returns:
          type: Manifest
        """
        return cls(project=ProjectConfig(name=project_name))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Manifest:
        """
        title: Build a manifest model from parsed TOML data.
        parameters:
          raw:
            type: Mapping[str, Any]
        returns:
          type: Manifest
        """
        project_raw = _require_table(raw, "project")
        build_raw = _require_table(raw, "build")
        toolchain_raw = _require_table(raw, "toolchain")
        dependencies_raw = raw.get("dependencies", {})
        if not isinstance(dependencies_raw, Mapping):
            raise ManifestError("dependencies must be a table")

        project = ProjectConfig(
            name=_require_string(project_raw, "name", "project"),
            version=_require_string(project_raw, "version", "project"),
            edition=_require_string(project_raw, "edition", "project"),
        )
        build = BuildConfig(
            entry=_require_string(build_raw, "entry", "build"),
            out_dir=_require_string(build_raw, "out_dir", "build"),
        )
        toolchain = ToolchainConfig(
            compiler=_require_string(toolchain_raw, "compiler", "toolchain"),
            linker=_require_string(toolchain_raw, "linker", "toolchain"),
        )

        dependencies: dict[str, DependencySpec] = {}
        for key, value in dependencies_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise ManifestError(
                    "dependency name must be a non-empty string"
                )
            dependencies[key] = DependencySpec.from_value(key, value)

        return cls(
            project=project,
            build=build,
            dependencies=dependencies,
            toolchain=toolchain,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        title: Serialize manifest model to dictionary.
        returns:
          type: dict[str, Any]
        """
        dependencies = {
            name: spec.to_dict()
            for name, spec in sorted(self.dependencies.items())
        }
        return {
            "project": {
                "name": self.project.name,
                "version": self.project.version,
                "edition": self.project.edition,
            },
            "build": {
                "entry": self.build.entry,
                "out_dir": self.build.out_dir,
            },
            "dependencies": dependencies,
            "toolchain": {
                "compiler": self.toolchain.compiler,
                "linker": self.toolchain.linker,
            },
        }


def _require_table(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = raw.get(key)
    if not isinstance(value, Mapping):
        raise ManifestError(f"{key} must be a table")
    return value


def _require_string(
    raw: Mapping[str, Any],
    key: str,
    section: str,
) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{section}.{key} must be a non-empty string")
    return value
