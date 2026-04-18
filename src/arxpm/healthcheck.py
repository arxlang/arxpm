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
from arxpm.manifest import MANIFEST_FILENAME, load_manifest

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
    title: Validate project manifest, environment, and toolchain availability.
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
