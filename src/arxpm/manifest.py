"""
title: Read and write .arxproject.toml manifests.
"""

from __future__ import annotations

import json
from pathlib import Path

from arxpm._toml import tomllib
from arxpm.errors import ManifestError
from arxpm.models import DependencySpec, Manifest

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
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a TOML table")
    return Manifest.from_dict(data)


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
        "",
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
    if manifest.dev_dependencies:
        lines.extend(
            [
                "",
                "[arxpm.dependencies-dev]",
            ]
        )
        lines.extend(
            _render_requirements_array(
                "dependencies",
                manifest.dev_dependencies,
            )
        )
    return "\n".join(lines) + "\n"


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
