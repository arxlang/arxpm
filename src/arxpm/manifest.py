"""
title: Read and write .arxproject.toml manifests.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import arx.settings as arx_settings

from arxpm._toml import tomllib
from arxpm.errors import ManifestError
from arxpm.models import (
    BuildConfig,
    DependencyGroupInclude,
    DependencySpec,
    EnvironmentConfig,
    Manifest,
    ProjectConfig,
    ToolchainConfig,
)

MANIFEST_FILENAME = arx_settings.DEFAULT_CONFIG_FILENAME
_DEFAULT_EDITION = "2026"


def manifest_path(directory: Path) -> Path:
    """
    title: Return the manifest path for a project directory.
    parameters:
      directory:
        type: Path
    returns:
      type: Path
    """
    return directory / MANIFEST_FILENAME


def create_default_manifest(project_name: str) -> Manifest:
    """
    title: Create a default v0 manifest.
    parameters:
      project_name:
        type: str
    returns:
      type: Manifest
    """
    return Manifest.default(project_name)


def load_manifest(directory: Path) -> Manifest:
    """
    title: Load a project manifest from a directory.
    parameters:
      directory:
        type: Path
    returns:
      type: Manifest
    """
    return load_manifest_file(manifest_path(directory))


def load_manifest_file(path: Path) -> Manifest:
    """
    title: Load a project manifest file.
    parameters:
      path:
        type: Path
    returns:
      type: Manifest
    """
    raw = _load_raw_manifest(path)
    _reject_removed_build_entry(raw)
    try:
        settings = cast(Any, arx_settings.load_settings(path))
    except arx_settings.ArxProjectError as exc:
        raise ManifestError(_normalize_settings_error(exc, path)) from exc
    return _manifest_from_settings(settings)


def save_manifest(directory: Path, manifest: Manifest) -> Path:
    """
    title: Save a project manifest into a directory.
    parameters:
      directory:
        type: Path
      manifest:
        type: Manifest
    returns:
      type: Path
    """
    path = manifest_path(directory)
    save_manifest_file(manifest, path)
    return path


def save_manifest_file(manifest: Manifest, path: Path) -> None:
    """
    title: Save a project manifest file.
    parameters:
      manifest:
        type: Manifest
      path:
        type: Path
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        arx_settings.write_settings(_settings_from_manifest(manifest), path)
    except arx_settings.ArxProjectError as exc:
        raise ManifestError(str(exc)) from exc


def render_manifest(manifest: Manifest) -> str:
    """
    title: Render a manifest model to TOML.
    parameters:
      manifest:
        type: Manifest
    returns:
      type: str
    """
    try:
        return arx_settings.dump_settings(_settings_from_manifest(manifest))
    except arx_settings.ArxProjectError as exc:
        raise ManifestError(str(exc)) from exc


def _load_raw_manifest(path: Path) -> Mapping[str, Any]:
    try:
        return cast(
            Mapping[str, Any], tomllib.loads(path.read_text(encoding="utf-8"))
        )
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(str(exc)) from exc


def _reject_removed_build_entry(raw: Mapping[str, Any]) -> None:
    build = raw.get("build")
    if not isinstance(build, Mapping):
        return
    if "entry" not in build:
        return
    raise ManifestError(
        "Invalid manifest: [build].entry is no longer supported; "
        "use build.package/build.mode instead"
    )


def _normalize_settings_error(
    error: arx_settings.ArxProjectError,
    path: Path,
) -> str:
    message = str(error)
    not_found_prefix = f"{MANIFEST_FILENAME} not found at "
    if message.startswith(not_found_prefix):
        return f"manifest not found: {path}"
    return message


def _manifest_from_settings(settings: Any) -> Manifest:
    project = ProjectConfig(
        name=settings.project.name,
        version=settings.project.version,
        edition=settings.project.edition or _DEFAULT_EDITION,
    )

    build_defaults = BuildConfig()
    build = BuildConfig(
        src_dir=(
            settings.build.src_dir
            if settings.build is not None
            and settings.build.src_dir is not None
            else build_defaults.src_dir
        ),
        out_dir=(
            settings.build.out_dir
            if settings.build is not None
            and settings.build.out_dir is not None
            else build_defaults.out_dir
        ),
        package=(
            getattr(settings.build, "package", None)
            if settings.build is not None
            else build_defaults.package
        ),
        mode=(
            getattr(settings.build, "mode", None)
            if settings.build is not None
            else build_defaults.mode
        ),
    )

    toolchain_defaults = ToolchainConfig()
    toolchain = ToolchainConfig(
        compiler=(
            settings.toolchain.compiler
            if settings.toolchain is not None
            and settings.toolchain.compiler is not None
            else toolchain_defaults.compiler
        ),
        linker=(
            settings.toolchain.linker
            if settings.toolchain is not None
            and settings.toolchain.linker is not None
            else toolchain_defaults.linker
        ),
    )

    environment = EnvironmentConfig.default()
    if settings.environment is not None:
        environment = EnvironmentConfig(
            kind=settings.environment.kind or "venv",
            path=settings.environment.path,
            name=settings.environment.name,
        )

    dependencies = _parse_settings_dependencies(
        settings.project.dependencies,
    )

    return Manifest(
        project=project,
        build=build,
        dependencies=dependencies,
        dependency_groups=_convert_dependency_groups(
            cast(
                dict[str, tuple[object, ...]],
                getattr(settings, "dependency_groups", {}),
            ),
        ),
        toolchain=toolchain,
        environment=environment,
    )


def _settings_from_manifest(manifest: Manifest) -> Any:
    project = cast(Any, arx_settings.Project)(
        name=manifest.project.name,
        version=manifest.project.version,
        edition=manifest.project.edition,
        dependencies=tuple(
            spec.to_requirement_string(name)
            for name, spec in sorted(manifest.dependencies.items())
        ),
    )

    build = cast(Any, arx_settings.Build)(
        src_dir=manifest.build.src_dir,
        out_dir=manifest.build.out_dir,
        package=manifest.build.package,
        mode=manifest.build.mode,
    )
    toolchain = cast(Any, arx_settings.Toolchain)(
        compiler=manifest.toolchain.compiler,
        linker=manifest.toolchain.linker,
    )

    environment: Any | None = None
    if not manifest.environment.is_default():
        environment = cast(Any, arx_settings.Environment)(
            kind=manifest.environment.kind,
            path=manifest.environment.path,
            name=manifest.environment.name,
        )

    project_kwargs: dict[str, Any] = {
        "project": project,
        "build": build,
        "toolchain": toolchain,
        "environment": environment,
    }
    if manifest.dependency_groups:
        if not _supports_settings_dependency_groups():
            raise ManifestError(
                "installed arx.settings does not support dependency-groups"
            )
        project_kwargs["dependency_groups"] = _settings_dependency_groups(
            manifest.dependency_groups,
        )

    return cast(Any, arx_settings.ArxProject)(**project_kwargs)


def _parse_settings_dependencies(
    dependencies: tuple[str, ...],
) -> dict[str, DependencySpec]:
    parsed: dict[str, DependencySpec] = {}
    for entry in dependencies:
        name, spec = DependencySpec.parse_requirement(entry)
        parsed[name] = spec
    return parsed


def _convert_dependency_groups(
    dependency_groups: dict[str, tuple[object, ...]],
) -> dict[str, tuple[str | DependencyGroupInclude, ...]]:
    converted: dict[str, tuple[str | DependencyGroupInclude, ...]] = {}
    for group_name, entries in dependency_groups.items():
        resolved_entries: list[str | DependencyGroupInclude] = []
        for entry in entries:
            if isinstance(entry, str):
                resolved_entries.append(entry)
                continue
            include_group = getattr(entry, "include_group", None)
            if isinstance(include_group, str):
                resolved_entries.append(DependencyGroupInclude(include_group))
                continue
            raise ManifestError(
                "unsupported dependency group entry from arx.settings: "
                f"{entry!r}"
            )
        converted[group_name] = tuple(resolved_entries)
    return converted


def _settings_dependency_groups(
    dependency_groups: Mapping[str, tuple[str | DependencyGroupInclude, ...]],
) -> dict[str, tuple[object, ...]]:
    converted: dict[str, tuple[object, ...]] = {}
    for group_name, entries in dependency_groups.items():
        rendered_entries: list[object] = []
        for entry in entries:
            if isinstance(entry, str):
                rendered_entries.append(entry)
                continue
            if isinstance(entry, DependencyGroupInclude):
                rendered_entries.append(
                    _make_settings_dependency_group_include(
                        entry.include_group
                    )
                )
                continue
            raise ManifestError(
                "unsupported dependency group entry for "
                f"{group_name!r}: {entry!r}"
            )
        converted[group_name] = tuple(rendered_entries)
    return converted


def _supports_settings_dependency_groups() -> bool:
    annotations = getattr(arx_settings.ArxProject, "__annotations__", {})
    return "dependency_groups" in annotations


def _make_settings_dependency_group_include(include_group: str) -> object:
    include_cls = getattr(arx_settings, "DependencyGroupInclude", None)
    if include_cls is None:
        raise ManifestError(
            "installed arx.settings does not expose DependencyGroupInclude"
        )
    return cast(Any, include_cls)(include_group=include_group)
