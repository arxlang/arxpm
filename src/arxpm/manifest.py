"""
title: Read and write .arxproject.toml manifests.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from arxpm._toml import tomllib
from arxpm.errors import ManifestError
from arxpm.models import DependencyGroupInclude, Manifest

MANIFEST_FILENAME = ".arxproject.toml"


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
    return Manifest.from_dict(raw)


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
    _validate_dependency_group_cycles(manifest)
    lines: list[str] = []
    data = manifest.to_dict()

    _append_table(lines, "project", cast(dict[str, Any], data["project"]))

    build_system = data.get("build-system")
    if isinstance(build_system, dict):
        _append_table(lines, "build-system", build_system)

    _append_table(lines, "build", cast(dict[str, Any], data["build"]))

    dependency_groups = data.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        lines.append("")
        lines.append("[dependency-groups]")
        _append_dependency_groups(lines, dependency_groups)

    environment = data.get("environment")
    if isinstance(environment, dict):
        _append_table(lines, "environment", environment)

    return "\n".join(lines).rstrip() + "\n"


def _validate_dependency_group_cycles(manifest: Manifest) -> None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(group_name: str) -> None:
        if group_name in visited:
            return
        if group_name in visiting:
            cycle = " -> ".join([*visiting, group_name])
            raise ManifestError(
                f"dependency-groups includes must not form cycles: {cycle}"
            )

        visiting.append(group_name)
        for entry in manifest.dependency_groups.get(group_name, ()):
            if isinstance(entry, DependencyGroupInclude):
                visit(entry.include_group)
        visiting.pop()
        visited.add(group_name)

    for group_name in manifest.dependency_groups:
        visit(group_name)


def _load_raw_manifest(path: Path) -> Mapping[str, Any]:
    try:
        return cast(
            Mapping[str, Any], tomllib.loads(path.read_text(encoding="utf-8"))
        )
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(str(exc)) from exc


def _append_table(
    lines: list[str],
    name: str,
    values: Mapping[str, Any],
) -> None:
    if lines:
        lines.append("")
    lines.append(f"[{name}]")
    for key, value in values.items():
        _append_key_value(lines, key, value)


def _append_key_value(lines: list[str], key: str, value: Any) -> None:
    if isinstance(value, list):
        lines.append(f"{key} = [")
        for entry in value:
            lines.append(f"  {_toml_value(entry)},")
        lines.append("]")
        return
    lines.append(f"{key} = {_toml_value(value)}")


def _append_dependency_groups(
    lines: list[str],
    dependency_groups: Mapping[str, Any],
) -> None:
    for group_name, entries in dependency_groups.items():
        lines.append(f"{_toml_key(group_name)} = [")
        for entry in entries:
            if isinstance(entry, Mapping):
                include_group = entry.get("include-group")
                lines.append(
                    f"  {{ include-group = {_toml_value(include_group)} }},"
                )
                continue
            lines.append(f"  {_toml_value(entry)},")
        lines.append("]")


def _toml_key(key: str) -> str:
    if key.replace("_", "").replace("-", "").isalnum():
        return key
    return _toml_value(key)


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        raise ManifestError("cannot render null values in manifest")
    return str(value)
