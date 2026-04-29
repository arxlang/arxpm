"""
title: Typed data models for Arx project manifests.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from arxpm.errors import ManifestError

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")
_GROUP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_GROUP_NORMALIZE_PATTERN = re.compile(r"[-_.]+")

ENVIRONMENT_KINDS = ("venv", "conda", "system")
DEFAULT_VENV_PATH = ".venv"
_DEFAULT_EDITION = "2026"
_DEFAULT_REQUIRES_ARX = ">=1.0"
_ARX_DISTRIBUTION_NAME = "arxlang"


@dataclass(slots=True, frozen=True)
class EnvironmentConfig:
    """
    title: Environment strategy configuration.
    attributes:
      kind:
        type: str
      path:
        type: str | None
      name:
        type: str | None
    """

    kind: str = "venv"
    path: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ENVIRONMENT_KINDS:
            allowed = ", ".join(ENVIRONMENT_KINDS)
            raise ManifestError(
                f"environment.kind must be one of: {allowed} "
                f"(got {self.kind!r})"
            )
        if self.path is not None and not self.path.strip():
            raise ManifestError("environment.path must be a non-empty string")
        if self.name is not None and not self.name.strip():
            raise ManifestError("environment.name must be a non-empty string")

        if self.kind == "venv":
            if self.name is not None:
                raise ManifestError(
                    "environment.name is not allowed when kind is 'venv'"
                )
            return

        if self.kind == "conda":
            if self.path is None and self.name is None:
                raise ManifestError(
                    "environment requires 'name' or 'path' "
                    "when kind is 'conda'"
                )
            return

        if self.kind == "system":
            if self.path is not None or self.name is not None:
                raise ManifestError(
                    "environment.path and environment.name are not "
                    "allowed when kind is 'system'"
                )

    @classmethod
    def default(cls) -> EnvironmentConfig:
        """
        title: Default environment configuration (local venv).
        returns:
          type: EnvironmentConfig
        """
        return cls(kind="venv")

    def is_default(self) -> bool:
        """
        title: Return True when the config matches the default.
        returns:
          type: bool
        """
        return self.kind == "venv" and self.path is None and self.name is None

    def resolved_path(self) -> str | None:
        """
        title: Resolve path with venv default fallback.
        returns:
          type: str | None
        """
        if self.kind == "venv" and self.path is None:
            return DEFAULT_VENV_PATH
        return self.path


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
      requires_arx:
        type: str | None
    """

    name: str
    version: str = "0.1.0"
    edition: str = "2026"
    requires_arx: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ManifestError("project.name must be a non-empty string")
        if not self.version.strip():
            raise ManifestError("project.version must be a non-empty string")
        if not self.edition.strip():
            raise ManifestError("project.edition must be a non-empty string")
        if self.requires_arx is None:
            return
        if not self.requires_arx.strip():
            raise ManifestError(
                "project.requires-arx must be a non-empty string"
            )
        try:
            SpecifierSet(self.requires_arx)
        except InvalidSpecifier as exc:
            raise ManifestError(
                "project.requires-arx must be a valid version specifier"
            ) from exc


@dataclass(slots=True, frozen=True)
class BuildConfig:
    """
    title: Build configuration.
    attributes:
      src_dir:
        type: str
      out_dir:
        type: str
      package:
        type: str | None
      mode:
        type: str | None
    """

    src_dir: str = "src"
    out_dir: str = "build"
    package: str | None = None
    mode: str | None = None

    def __post_init__(self) -> None:
        if not self.src_dir.strip():
            raise ManifestError("build.src_dir must be a non-empty string")
        if not self.out_dir.strip():
            raise ManifestError("build.out_dir must be a non-empty string")
        if self.package is not None and not self.package.strip():
            raise ManifestError("build.package must be a non-empty string")
        if self.mode is not None and self.mode not in {"lib", "app"}:
            raise ManifestError("build.mode must be 'lib' or 'app'")


@dataclass(slots=True, frozen=True)
class BuildSystemConfig:
    """
    title: Build-system dependency configuration.
    attributes:
      dependencies:
        type: tuple[str, Ellipsis]
    """

    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for index, dependency in enumerate(self.dependencies):
            _validate_build_requirement(
                dependency,
                f"build-system.dependencies[{index}]",
            )


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
      version_constraint:
        type: str | None
    """

    source: str | None = None
    path: str | None = None
    git: str | None = None
    version_constraint: str | None = None

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
        if self.version_constraint is None:
            return
        if self.source is None:
            raise ManifestError(
                "dependency version constraint is only allowed for "
                "registry dependencies"
            )
        if not self.version_constraint.strip():
            raise ManifestError(
                "dependency version constraint must be non-empty"
            )
        try:
            SpecifierSet(self.version_constraint)
        except InvalidSpecifier as exc:
            raise ManifestError(
                "dependency version constraint must be a valid version "
                "specifier"
            ) from exc

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
    def registry(
        cls,
        version_constraint: str | None = None,
    ) -> DependencySpec:
        """
        title: Create a registry placeholder dependency.
        parameters:
          version_constraint:
            type: str | None
        returns:
          type: DependencySpec
        """
        return cls(
            source="registry",
            version_constraint=version_constraint,
        )

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

        try:
            requirement = Requirement(raw)
        except InvalidRequirement as exc:
            raise ManifestError(
                f"dependency {text!r} must be a valid Python requirement"
            ) from exc
        _validate_name(requirement.name, text)
        if requirement.extras:
            raise ManifestError(f"dependency {text!r} must not use extras")
        if requirement.marker is not None:
            raise ManifestError(
                f"dependency {text!r} must not use environment markers"
            )
        if requirement.url is not None:
            raise ManifestError(
                f"dependency {text!r} must use '<name> @ <path-or-git>' "
                "for direct references"
            )
        version_constraint = str(requirement.specifier) or None
        return requirement.name, cls.registry(version_constraint)

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
            if self.version_constraint is not None:
                return f"{name}{self.version_constraint}"
            return name
        if self.path is not None:
            return f"{name} @ {self.path}"
        if self.git is not None:
            return f"{name} @ git+{self.git}"
        raise ManifestError("invalid dependency state")


@dataclass(slots=True, frozen=True)
class DependencyGroupInclude:
    """
    title: Include one named dependency group inside another group.
    attributes:
      include_group:
        type: str
    """

    include_group: str


DependencyGroupEntry = str | DependencyGroupInclude


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
      dependency_groups:
        type: dict[str, tuple[DependencyGroupEntry, Ellipsis]]
      build_system:
        type: BuildSystemConfig | None
      environment:
        type: EnvironmentConfig
    """

    project: ProjectConfig
    build: BuildConfig = field(default_factory=BuildConfig)
    dependencies: dict[str, DependencySpec] = field(default_factory=dict)
    dependency_groups: dict[str, tuple[DependencyGroupEntry, ...]] = field(
        default_factory=dict
    )
    build_system: BuildSystemConfig | None = None
    environment: EnvironmentConfig = field(
        default_factory=EnvironmentConfig.default,
    )

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
        requires_arx = _default_requires_arx()
        return cls(
            project=ProjectConfig(
                name=project_name,
                requires_arx=requires_arx,
            ),
            build_system=BuildSystemConfig(
                dependencies=(f"{_ARX_DISTRIBUTION_NAME}{requires_arx}",),
            ),
        )

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

        allowed_top_level = {
            "project",
            "build-system",
            "build",
            "environment",
            "dependency-groups",
        }
        if "toolchain" in raw:
            raise ManifestError(
                ".arxproject.toml does not support [toolchain] sections. "
                "Declare compiler/build requirements in [build-system] "
                'using dependencies = ["arxlang..."].'
            )
        extra_top_level = set(raw.keys()) - allowed_top_level
        if extra_top_level:
            unknown = ", ".join(sorted(extra_top_level))
            raise ManifestError(
                f"manifest has unknown top-level keys: {unknown}"
            )

        project_raw = _require_table(raw, "project")

        project = ProjectConfig(
            name=_require_string(project_raw, "name", "project"),
            version=_require_string(project_raw, "version", "project"),
            edition=_optional_string(
                project_raw,
                "edition",
                "project",
                _DEFAULT_EDITION,
            ),
            requires_arx=_optional_optional_string(
                project_raw,
                "requires-arx",
                "project",
                None,
            ),
        )

        build_system = _parse_build_system(raw.get("build-system"))

        build_raw = raw.get("build")
        if build_raw is None:
            build = BuildConfig()
        else:
            if not isinstance(build_raw, Mapping):
                raise ManifestError("build must be a table")
            if "entry" in build_raw:
                raise ManifestError(
                    "Invalid manifest: [build].entry is no longer supported; "
                    "use build.package/build.mode instead"
                )
            build_defaults = BuildConfig()
            build = BuildConfig(
                src_dir=_optional_string(
                    build_raw,
                    "src_dir",
                    "build",
                    build_defaults.src_dir,
                ),
                out_dir=_optional_string(
                    build_raw,
                    "out_dir",
                    "build",
                    build_defaults.out_dir,
                ),
                package=_optional_optional_string(
                    build_raw,
                    "package",
                    "build",
                    build_defaults.package,
                ),
                mode=_optional_optional_string(
                    build_raw,
                    "mode",
                    "build",
                    build_defaults.mode,
                ),
            )

        dependencies = _parse_requirements(
            project_raw.get("dependencies", []),
            "project.dependencies",
        )

        dependency_groups = _parse_dependency_groups(
            raw.get("dependency-groups")
        )
        environment = _parse_environment(raw.get("environment"))

        return cls(
            project=project,
            build=build,
            dependencies=dependencies,
            dependency_groups=dependency_groups,
            build_system=build_system,
            environment=environment,
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
        }
        if self.project.requires_arx is not None:
            project["requires-arx"] = self.project.requires_arx
        if self.dependencies:
            project["dependencies"] = [
                spec.to_requirement_string(name)
                for name, spec in sorted(self.dependencies.items())
            ]
        build: dict[str, Any] = {
            "src_dir": self.build.src_dir,
            "out_dir": self.build.out_dir,
        }
        if self.build.package is not None:
            build["package"] = self.build.package
        if self.build.mode is not None:
            build["mode"] = self.build.mode

        data: dict[str, Any] = {
            "project": project,
            "build": build,
        }
        if self.build_system is not None:
            data["build-system"] = {
                "dependencies": list(self.build_system.dependencies),
            }
        if self.dependency_groups:
            data["dependency-groups"] = {
                name: [
                    (
                        {"include-group": entry.include_group}
                        if isinstance(entry, DependencyGroupInclude)
                        else entry
                    )
                    for entry in entries
                ]
                for name, entries in self.dependency_groups.items()
            }
        if not self.environment.is_default():
            env_data: dict[str, Any] = {"kind": self.environment.kind}
            if self.environment.path is not None:
                env_data["path"] = self.environment.path
            if self.environment.name is not None:
                env_data["name"] = self.environment.name
            data["environment"] = env_data
        return data


def effective_build_system_dependencies(manifest: Manifest) -> list[str]:
    """
    title: Return build-system dependencies after Arx default injection.
    parameters:
      manifest:
        type: Manifest
    returns:
      type: list[str]
    """
    dependencies = (
        list(manifest.build_system.dependencies)
        if manifest.build_system is not None
        else []
    )
    if _has_requirement_named(dependencies, _ARX_DISTRIBUTION_NAME):
        return dependencies

    arx_dependency = _ARX_DISTRIBUTION_NAME
    if manifest.project.requires_arx is not None:
        arx_dependency = f"{arx_dependency}{manifest.project.requires_arx}"
    return [arx_dependency, *dependencies]


def _default_requires_arx() -> str:
    try:
        version = importlib_metadata.version(_ARX_DISTRIBUTION_NAME)
    except importlib_metadata.PackageNotFoundError:
        return _DEFAULT_REQUIRES_ARX
    try:
        public_version = Version(version).public
    except InvalidVersion:
        return _DEFAULT_REQUIRES_ARX
    return f">={public_version}"


def _has_requirement_named(
    dependencies: Sequence[str],
    name: str,
) -> bool:
    normalized_name = _normalize_distribution_name(name)
    return any(
        _normalize_distribution_name(Requirement(dependency).name)
        == normalized_name
        for dependency in dependencies
    )


def _validate_build_requirement(dependency: str, label: str) -> None:
    if not isinstance(dependency, str) or not dependency.strip():
        raise ManifestError(f"{label} must be a non-empty string")
    try:
        Requirement(dependency)
    except InvalidRequirement as exc:
        raise ManifestError(
            f"{label} must be a valid Python requirement"
        ) from exc


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_build_system(raw: Any) -> BuildSystemConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ManifestError("build-system must be a table")

    allowed = {"dependencies"}
    extra = set(raw.keys()) - allowed
    if extra:
        unknown = ", ".join(sorted(extra))
        raise ManifestError(
            f"build-system has unknown keys: {unknown} (allowed: dependencies)"
        )

    return BuildSystemConfig(
        dependencies=_parse_build_system_dependencies(
            raw.get("dependencies", ()),
        )
    )


def _parse_build_system_dependencies(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str) or isinstance(raw, Mapping):
        raise ManifestError(
            "build-system.dependencies must be an array of strings"
        )
    if not isinstance(raw, Sequence):
        raise ManifestError(
            "build-system.dependencies must be an array of strings"
        )

    dependencies: list[str] = []
    for index, entry in enumerate(raw):
        _validate_build_requirement(
            entry,
            f"build-system.dependencies[{index}]",
        )
        dependencies.append(entry)
    return tuple(dependencies)


def _parse_environment(raw: Any) -> EnvironmentConfig:
    if raw is None:
        return EnvironmentConfig.default()
    if not isinstance(raw, Mapping):
        raise ManifestError("environment must be a table")

    allowed = {"kind", "path", "name"}
    extra = set(raw.keys()) - allowed
    if extra:
        unknown = ", ".join(sorted(extra))
        raise ManifestError(
            f"environment has unknown keys: {unknown} "
            f"(allowed: kind, path, name)"
        )

    kind = raw.get("kind", "venv")
    if not isinstance(kind, str):
        raise ManifestError("environment.kind must be a string")

    return EnvironmentConfig(
        kind=kind,
        path=_optional_nullable_string(raw, "path", "environment"),
        name=_optional_nullable_string(raw, "name", "environment"),
    )


def _optional_nullable_string(
    raw: Mapping[str, Any],
    key: str,
    section: str,
) -> str | None:
    if key not in raw:
        return None
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"{section}.{key} must be a string")
    if not value.strip():
        raise ManifestError(f"{section}.{key} must be a non-empty string")
    return value


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


def _optional_string(
    raw: Mapping[str, Any],
    key: str,
    section: str,
    default: str,
) -> str:
    if key not in raw:
        return default
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{section}.{key} must be a non-empty string")
    return value


def _optional_optional_string(
    raw: Mapping[str, Any],
    key: str,
    section: str,
    default: str | None,
) -> str | None:
    if key not in raw:
        return default
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{section}.{key} must be a non-empty string")
    return value


def _parse_dependency_groups(
    raw: Any,
) -> dict[str, tuple[DependencyGroupEntry, ...]]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ManifestError("dependency-groups must be a table")

    normalized_names: dict[str, str] = {}
    parsed: dict[str, tuple[DependencyGroupEntry, ...]] = {}
    for group_name, raw_entries in raw.items():
        if not isinstance(group_name, str):
            raise ManifestError("dependency-groups keys must be strings")
        _validate_group_name(
            group_name, f"dependency-groups key {group_name!r}"
        )
        normalized = _normalize_group_name(group_name)
        if normalized in normalized_names:
            raise ManifestError(
                "dependency-groups names must be unique after normalization: "
                f"{group_name!r} conflicts with "
                f"{normalized_names[normalized]!r}"
            )
        normalized_names[normalized] = group_name
        parsed[group_name] = _parse_dependency_group_entries(
            group_name,
            raw_entries,
        )

    for group_name, entries in parsed.items():
        for index, entry in enumerate(entries):
            if not isinstance(entry, DependencyGroupInclude):
                continue
            normalized = _normalize_group_name(entry.include_group)
            if normalized not in normalized_names:
                raise ManifestError(
                    "dependency-groups."
                    f"{group_name}[{index}] includes unknown group "
                    f"{entry.include_group!r}"
                )

    return parsed


def _parse_dependency_group_entries(
    group_name: str,
    raw: Any,
) -> tuple[DependencyGroupEntry, ...]:
    if isinstance(raw, str) or isinstance(raw, Mapping):
        raise ManifestError(f"dependency-groups.{group_name} must be an array")
    if not isinstance(raw, Sequence):
        raise ManifestError(f"dependency-groups.{group_name} must be an array")

    entries: list[DependencyGroupEntry] = []
    for index, entry in enumerate(raw):
        if isinstance(entry, str):
            DependencySpec.parse_requirement(entry)
            entries.append(entry)
            continue
        if not isinstance(entry, Mapping):
            raise ManifestError(
                "dependency-groups."
                f"{group_name}[{index}] must be a string or "
                '{"include-group" = "name"}'
            )
        keys = set(entry.keys())
        if keys != {"include-group"}:
            raise ManifestError(
                "dependency-groups."
                f"{group_name}[{index}] must only use include-group"
            )
        include_group = entry.get("include-group")
        if not isinstance(include_group, str):
            raise ManifestError(
                "dependency-groups."
                f"{group_name}[{index}].include-group must be a string"
            )
        _validate_group_name(
            include_group,
            f"dependency-groups.{group_name}[{index}].include-group",
        )
        entries.append(DependencyGroupInclude(include_group))
    return tuple(entries)


def _validate_group_name(name: str, location: str) -> None:
    if _GROUP_NAME_PATTERN.fullmatch(name) is not None:
        return
    raise ManifestError(f"{location} must match [A-Za-z0-9][A-Za-z0-9._-]*")


def _normalize_group_name(name: str) -> str:
    return _GROUP_NORMALIZE_PATTERN.sub("-", name).lower()
