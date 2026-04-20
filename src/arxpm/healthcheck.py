"""
title: Environment and project health checks for arxpm.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from arxpm.environment import EnvironmentFactory, build_environment
from arxpm.errors import ArxpmError
from arxpm.layout import is_valid_package_name
from arxpm.manifest import MANIFEST_FILENAME, load_manifest
from arxpm.models import Manifest

WhichFn = Callable[[str], str | None]


@dataclass(slots=True, frozen=True)
class HealthCheck:
    """
    title: Single healthcheck entry.
    attributes:
      name:
        type: str
      ok:
        type: bool
      message:
        type: str
    """

    name: str
    ok: bool
    message: str


@dataclass(slots=True, frozen=True)
class HealthReport:
    """
    title: Healthcheck command report.
    attributes:
      checks:
        type: tuple[HealthCheck, Ellipsis]
    """

    checks: tuple[HealthCheck, ...]

    @property
    def ok(self) -> bool:
        """
        title: Return overall healthcheck status.
        returns:
          type: bool
        """
        return all(check.ok for check in self.checks)


class HealthCheckService:
    """
    title: Validate project manifest, layout, environment, and toolchain.
    attributes:
      _environment_factory:
        type: EnvironmentFactory
      _which:
        type: WhichFn
    """

    _environment_factory: EnvironmentFactory
    _which: WhichFn

    def __init__(
        self,
        environment_factory: EnvironmentFactory | None = None,
        which: WhichFn = shutil.which,
    ) -> None:
        self._environment_factory = environment_factory or build_environment
        self._which = which

    def run(self, directory: Path) -> HealthReport:
        """
        title: Collect health checks for the current project.
        parameters:
          directory:
            type: Path
        returns:
          type: HealthReport
        """
        checks: list[HealthCheck] = []

        manifest_path = directory / MANIFEST_FILENAME
        manifest_ok = manifest_path.exists()
        checks.append(
            HealthCheck(
                name=MANIFEST_FILENAME,
                ok=manifest_ok,
                message=(
                    f"{MANIFEST_FILENAME} found"
                    if manifest_ok
                    else f"{MANIFEST_FILENAME} missing"
                ),
            )
        )

        if not manifest_ok:
            checks.append(
                HealthCheck(
                    name="manifest parsing",
                    ok=False,
                    message="skipped: manifest missing",
                )
            )
            return HealthReport(checks=tuple(checks))

        try:
            manifest = load_manifest(directory)
        except ArxpmError as exc:
            checks.append(
                HealthCheck(
                    name="manifest parsing",
                    ok=False,
                    message=str(exc),
                )
            )
            return HealthReport(checks=tuple(checks))

        checks.append(
            HealthCheck(
                name="manifest parsing",
                ok=True,
                message="manifest parsed",
            )
        )
        checks.extend(_layout_checks(manifest, directory))

        uv_ok = self._which("uv") is not None
        checks.append(
            HealthCheck(
                name="uv",
                ok=uv_ok,
                message="uv is available" if uv_ok else "uv is missing",
            )
        )

        compiler = manifest.toolchain.compiler
        compiler_ok = self._which(compiler) is not None
        checks.append(
            HealthCheck(
                name=f"compiler ({compiler})",
                ok=compiler_ok,
                message=(
                    f"{compiler} is available"
                    if compiler_ok
                    else f"{compiler} is missing"
                ),
            )
        )

        try:
            environment = self._environment_factory(manifest, directory)
            env_description = environment.describe()
            environment.validate()
            env_ok = True
            env_message = f"{env_description} reachable"
        except ArxpmError as exc:
            env_ok = False
            env_message = str(exc)
        checks.append(
            HealthCheck(
                name="environment",
                ok=env_ok,
                message=env_message,
            )
        )

        return HealthReport(checks=tuple(checks))


def _layout_checks(
    manifest: Manifest,
    directory: Path,
) -> tuple[HealthCheck, ...]:
    src_dir = manifest.build.src_dir or "src"
    package = manifest.build.package or manifest.project.name
    source_root = directory / src_dir
    package_root = source_root / package
    init_file = package_root / "__init__.x"
    main_file = package_root / "main.x"
    mode = manifest.build.mode or ("app" if main_file.exists() else "lib")

    checks = [
        HealthCheck(
            name="package name",
            ok=is_valid_package_name(package),
            message=(
                f"resolved package name is valid: {package}"
                if is_valid_package_name(package)
                else (
                    "Invalid manifest: project.name is not a valid package "
                    "name; set [build].package explicitly"
                    if manifest.build.package is None
                    else f"Invalid manifest: build.package is not a valid "
                    f"package name: {package!r}"
                )
            ),
        ),
        HealthCheck(
            name="source root",
            ok=source_root.is_dir(),
            message=(
                f"source root found: {source_root}"
                if source_root.is_dir()
                else (
                    "Invalid project layout: source root not found: "
                    f"{source_root}"
                )
            ),
        ),
        HealthCheck(
            name="package root",
            ok=package_root.is_dir(),
            message=(
                f"package root found: {package_root}"
                if package_root.is_dir()
                else (
                    "Invalid project layout: package root not found: "
                    f"{package_root}"
                )
            ),
        ),
        HealthCheck(
            name="__init__.x",
            ok=init_file.is_file(),
            message=(
                f"__init__.x found at {init_file}"
                if init_file.is_file()
                else (
                    "Invalid project layout: missing __init__.x at "
                    f"{init_file}"
                )
            ),
        ),
    ]

    if mode == "app":
        main_ok = main_file.is_file()
        if manifest.build.mode == "app":
            main_message = (
                f"main.x found at {main_file}"
                if main_ok
                else (
                    'Invalid project layout: [build].mode = "app" '
                    f"requires main.x at {main_file}"
                )
            )
        else:
            main_message = (
                f"main.x found at {main_file}; inferred app mode"
                if main_ok
                else (
                    f"main.x not required for inferred lib mode at {main_file}"
                )
            )
    else:
        main_ok = not main_file.exists()
        if manifest.build.mode == "lib":
            main_message = (
                f"main.x absent at {main_file}"
                if main_ok
                else (
                    'Invalid project layout: [build].mode = "lib" does not '
                    f"allow main.x at {main_file}"
                )
            )
        else:
            main_message = (
                f"main.x absent at {main_file}; inferred lib mode"
                if main_ok
                else (
                    "Invalid project layout: lib projects must not define "
                    f"main.x at {main_file}"
                )
            )

    checks.append(
        HealthCheck(
            name="main.x",
            ok=main_ok,
            message=main_message,
        )
    )

    return tuple(checks)
