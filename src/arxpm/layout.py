"""
title: Resolve and validate Arx project build layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from arxpm.errors import ManifestError
from arxpm.models import Manifest

_PACKAGE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True, frozen=True)
class ResolvedBuildConfig:
    """
    title: Effective build layout for an Arx project.
    attributes:
      src_dir:
        type: str
      out_dir:
        type: str
      package:
        type: str
      mode:
        type: str
      source_root:
        type: Path
      package_root:
        type: Path
      init_file:
        type: Path
      main_file:
        type: Path
    """

    src_dir: str
    out_dir: str
    package: str
    mode: str
    source_root: Path
    package_root: Path
    init_file: Path
    main_file: Path

    @property
    def target_file(self) -> Path:
        """
        title: Return the default source file for the active build mode.
        returns:
          type: Path
        """
        if self.mode == "app":
            return self.main_file
        return self.init_file


def resolve_build_config(
    manifest: Manifest,
    project_root: Path,
) -> ResolvedBuildConfig:
    """
    title: Resolve and validate effective build settings for a project.
    parameters:
      manifest:
        type: Manifest
      project_root:
        type: Path
    returns:
      type: ResolvedBuildConfig
    """
    src_dir = manifest.build.src_dir or "src"
    out_dir = manifest.build.out_dir or "build"
    package = manifest.build.package or manifest.project.name

    if not _is_valid_package_name(package):
        if manifest.build.package is None:
            raise ManifestError(
                "Invalid manifest: project.name is not a valid package "
                "name; set [build].package explicitly"
            )
        raise ManifestError(
            f"Invalid manifest: build.package is not a valid package "
            f"name: {package!r}"
        )

    source_root = project_root / src_dir
    package_root = source_root / package
    init_file = package_root / "__init__.x"
    main_file = package_root / "main.x"

    explicit_mode = manifest.build.mode
    if explicit_mode is None:
        mode = "app" if main_file.exists() else "lib"
    else:
        mode = explicit_mode

    resolved = ResolvedBuildConfig(
        src_dir=src_dir,
        out_dir=out_dir,
        package=package,
        mode=mode,
        source_root=source_root,
        package_root=package_root,
        init_file=init_file,
        main_file=main_file,
    )
    _validate_layout(resolved, explicit_mode)
    return resolved


def is_valid_package_name(name: str) -> bool:
    """
    title: Return whether a name is a valid Arx package identifier.
    parameters:
      name:
        type: str
    returns:
      type: bool
    """
    return _is_valid_package_name(name)


def _is_valid_package_name(name: str) -> bool:
    return bool(_PACKAGE_PATTERN.match(name))


def _validate_layout(
    resolved: ResolvedBuildConfig,
    explicit_mode: str | None,
) -> None:
    if not resolved.source_root.is_dir():
        raise ManifestError(
            "Invalid project layout: source root not found: "
            f"{resolved.source_root}"
        )
    if not resolved.package_root.is_dir():
        raise ManifestError(
            "Invalid project layout: package root not found: "
            f"{resolved.package_root}"
        )
    if not resolved.init_file.is_file():
        raise ManifestError(
            "Invalid project layout: missing __init__.x at "
            f"{resolved.init_file}"
        )

    if resolved.mode == "app":
        if not resolved.main_file.is_file():
            raise ManifestError(
                'Invalid project layout: [build].mode = "app" requires '
                f"main.x at {resolved.main_file}"
            )
        return

    if resolved.main_file.exists():
        if explicit_mode == "lib":
            raise ManifestError(
                'Invalid project layout: [build].mode = "lib" does not '
                f"allow main.x at {resolved.main_file}"
            )
        raise ManifestError(
            "Invalid project layout: lib projects must not define "
            f"main.x at {resolved.main_file}"
        )
