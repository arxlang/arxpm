"""
title: Typed data models for Arx project manifests.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from arxpm.errors import ManifestError

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


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

    entry: str = "src/main.x"
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
    def parse_requirement(cls, text: str) -> tuple[str, DependencySpec]:
        """
        title: Parse a PEP 508-lite requirement string into (name, spec).
        parameters:
          text:
            type: str
        returns:
          type: tuple[str, DependencySpec]
        """
        if not isinstance(text, str):
            raise ManifestError(
                f"dependency entry must be a string, got {type(text).__name__}"
            )
        raw = text.strip()
        if not raw:
            raise ManifestError("dependency entry must be a non-empty string")

        if "@" in raw:
            name_part, _, ref_part = raw.partition("@")
            name = name_part.strip()
            ref = ref_part.strip()
            if not ref:
                raise ManifestError(
                    f"dependency {text!r} must specify a reference after '@'"
                )
            _validate_name(name, text)
            if ref.startswith("git+"):
                return name, cls.from_git(ref[len("git+") :])
            return name, cls.from_path(ref)

        name = raw
        _validate_name(name, text)
        return name, cls.registry()

    def to_requirement_string(self, name: str) -> str:
        """
        title: Render this spec back to a PEP 508-lite requirement string.
        parameters:
          name:
            type: str
        returns:
          type: str
        """
        if self.source is not None:
            return name
        if self.path is not None:
            return f"{name} @ {self.path}"
        if self.git is not None:
            return f"{name} @ git+{self.git}"
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
      dev_dependencies:
        type: dict[str, DependencySpec]
      toolchain:
        type: ToolchainConfig
    """

    project: ProjectConfig
    build: BuildConfig = field(default_factory=BuildConfig)
    dependencies: dict[str, DependencySpec] = field(default_factory=dict)
    dev_dependencies: dict[str, DependencySpec] = field(default_factory=dict)
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
        if "dependencies" in raw:
            raise ManifestError(
                "top-level [dependencies] table is no longer supported; "
                "move entries into project.dependencies as PEP 508-style "
                'strings (e.g. dependencies = ["pyyaml", '
                '"local_lib @ ../local_lib"])'
            )

        project_raw = _require_table(raw, "project")
        build_raw = _require_table(raw, "build")
        toolchain_raw = _require_table(raw, "toolchain")

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

        dependencies = _parse_requirements(
            project_raw.get("dependencies", []),
            "project.dependencies",
        )

        arxpm_raw = raw.get("arxpm", {})
        if arxpm_raw and not isinstance(arxpm_raw, Mapping):
            raise ManifestError("arxpm must be a table")
        dev_raw = arxpm_raw.get("dependencies-dev", {}) if arxpm_raw else {}
        if dev_raw and not isinstance(dev_raw, Mapping):
            raise ManifestError("arxpm.dependencies-dev must be a table")
        dev_dependencies = _parse_requirements(
            dev_raw.get("dependencies", []) if dev_raw else [],
            "arxpm.dependencies-dev.dependencies",
        )

        return cls(
            project=project,
            build=build,
            dependencies=dependencies,
            dev_dependencies=dev_dependencies,
            toolchain=toolchain,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        title: Serialize manifest model to dictionary.
        returns:
          type: dict[str, Any]
        """
        project: dict[str, Any] = {
            "name": self.project.name,
            "version": self.project.version,
            "edition": self.project.edition,
            "dependencies": [
                spec.to_requirement_string(name)
                for name, spec in sorted(self.dependencies.items())
            ],
        }
        data: dict[str, Any] = {
            "project": project,
            "build": {
                "entry": self.build.entry,
                "out_dir": self.build.out_dir,
            },
            "toolchain": {
                "compiler": self.toolchain.compiler,
                "linker": self.toolchain.linker,
            },
        }
        if self.dev_dependencies:
            data["arxpm"] = {
                "dependencies-dev": {
                    "dependencies": [
                        spec.to_requirement_string(name)
                        for name, spec in sorted(self.dev_dependencies.items())
                    ],
                },
            }
        return data


def _parse_requirements(
    raw: Any,
    label: str,
) -> dict[str, DependencySpec]:
    if isinstance(raw, str) or isinstance(raw, Mapping):
        raise ManifestError(
            f"{label} must be an array of strings (e.g. "
            '["pyyaml", "local_lib @ ../local_lib"])'
        )
    if not isinstance(raw, Sequence):
        raise ManifestError(f"{label} must be an array of strings")

    parsed: dict[str, DependencySpec] = {}
    for entry in raw:
        name, spec = DependencySpec.parse_requirement(entry)
        if name in parsed:
            raise ManifestError(
                f"{label} contains duplicate entry for {name!r}"
            )
        parsed[name] = spec
    return parsed


def _validate_name(name: str, original: str) -> None:
    if not name:
        raise ManifestError(
            f"dependency {original!r} is missing a name before '@'"
        )
    if not _NAME_PATTERN.match(name):
        raise ManifestError(
            f"dependency name {name!r} must match [A-Za-z_][A-Za-z0-9_-]*"
        )


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
