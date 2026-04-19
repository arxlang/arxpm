"""
title: Read and write .arxproject.toml manifests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, cast

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

ArxProject = Any


class _SettingsLoader(Protocol):
    def __call__(
        self,
        content: str,
        source_path: Path | None = None,
    ) -> ArxProject: ...


try:
    from arx.settings import (
        DEFAULT_CONFIG_FILENAME as _DEFAULT_CONFIG_FILENAME,
    )
    from arx.settings import ArxProjectError as _ArxProjectError
    from arx.settings import (
        load_settings_from_text as _load_settings_from_text,
    )
except ImportError:  # pragma: no cover - compatibility fallback
    MANIFEST_FILENAME = ".arxproject.toml"
    ArxProjectError: type[Exception] = Exception
    load_settings_from_text: _SettingsLoader | None = None
else:
    MANIFEST_FILENAME = _DEFAULT_CONFIG_FILENAME
    ArxProjectError = cast(type[Exception], _ArxProjectError)
    load_settings_from_text = cast(_SettingsLoader, _load_settings_from_text)

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
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")

    raw = _load_raw_manifest(path)
    manifest = _load_manifest_with_arx_settings(path)
    if manifest is not None:
        return manifest
    return Manifest.from_dict(raw)


def _load_raw_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a TOML table")
    return data


def _load_manifest_with_arx_settings(path: Path) -> Manifest | None:
    if load_settings_from_text is None:
        return None

    content = path.read_text(encoding="utf-8")
    try:
        settings = load_settings_from_text(
            content,
            source_path=path.resolve(),
        )
    except ArxProjectError:
        return None

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
    path.write_text(render_manifest(manifest), encoding="utf-8")


def render_manifest(manifest: Manifest) -> str:
    """
    title: Render a manifest model to TOML.
    parameters:
      manifest:
        type: Manifest
    returns:
      type: str
    """
    lines: list[str] = [
        "[project]",
        f"name = {_quote(manifest.project.name)}",
        f"version = {_quote(manifest.project.version)}",
        f"edition = {_quote(manifest.project.edition)}",
    ]
    lines.extend(
        _render_requirements_array(
            "dependencies",
            manifest.dependencies,
        )
    )
    lines.extend(
        [
            "",
            "[build]",
            f"src_dir = {_quote(manifest.build.src_dir)}",
            f"entry = {_quote(manifest.build.entry)}",
            f"out_dir = {_quote(manifest.build.out_dir)}",
            "",
            "[toolchain]",
            f"compiler = {_quote(manifest.toolchain.compiler)}",
            f"linker = {_quote(manifest.toolchain.linker)}",
        ]
    )
    if manifest.dependency_groups:
        lines.extend(["", "[dependency-groups]"])
        for group_name, entries in manifest.dependency_groups.items():
            lines.extend(_render_dependency_group_array(group_name, entries))
    if not manifest.environment.is_default():
        lines.extend(
            [
                "",
                "[environment]",
                f"kind = {_quote(manifest.environment.kind)}",
            ]
        )
        if manifest.environment.path is not None:
            lines.append(f"path = {_quote(manifest.environment.path)}")
        if manifest.environment.name is not None:
            lines.append(f"name = {_quote(manifest.environment.name)}")
    return "\n".join(lines) + "\n"


def _manifest_from_settings(settings: ArxProject) -> Manifest:
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
        entry=(
            settings.build.entry
            if settings.build is not None and settings.build.entry is not None
            else build_defaults.entry
        ),
        out_dir=(
            settings.build.out_dir
            if settings.build is not None
            and settings.build.out_dir is not None
            else build_defaults.out_dir
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

    dependencies = _parse_settings_dependency_group(
        settings.project.dependencies,
    )

    return Manifest(
        project=project,
        build=build,
        dependencies=dependencies,
        dependency_groups=_convert_dependency_groups(
            settings.dependency_groups,
        ),
        toolchain=toolchain,
        environment=environment,
    )


def _parse_settings_dependency_group(
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


def _render_dependency_group_array(
    name: str,
    entries: tuple[object, ...],
) -> list[str]:
    if not entries:
        return [f"{name} = []"]
    lines = [f"{name} = ["]
    for entry in entries:
        if isinstance(entry, str):
            lines.append(f"  {_quote(entry)},")
            continue
        if isinstance(entry, DependencyGroupInclude):
            lines.append(
                f"  {{ include-group = {_quote(entry.include_group)} }},"
            )
            continue
        raise ManifestError(
            f"unsupported dependency group entry for {name!r}: {entry!r}"
        )
    lines.append("]")
    return lines


def _render_requirements_array(
    key: str,
    entries: dict[str, DependencySpec],
) -> list[str]:
    if not entries:
        return [f"{key} = []"]
    rendered = [
        _quote(spec.to_requirement_string(name))
        for name, spec in sorted(entries.items())
    ]
    lines = [f"{key} = ["]
    lines.extend(f"  {value}," for value in rendered)
    lines.append("]")
    return lines


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)
