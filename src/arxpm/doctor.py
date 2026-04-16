"""
title: Environment health checks for arxpm.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arxpm.errors import ManifestError
from arxpm.manifest import MANIFEST_FILENAME
from arxpm.pixi import PIXI_FILENAME, PixiService


class DoctorPixiAdapter(Protocol):
    """
    title: Doctor-level pixi adapter protocol.
    """

    def is_available(self) -> bool:
        """
        title: Return whether pixi is available.
        returns:
          type: bool
        """

    def pixi_path(self, directory: Path) -> Path:
        """
        title: Return pixi.toml path.
        parameters:
          directory:
            type: Path
        returns:
          type: Path
        """

    def declared_dependencies(self, directory: Path) -> set[str]:
        """
        title: Return declared dependencies from pixi.toml.
        parameters:
          directory:
            type: Path
        returns:
          type: set[str]
        """


@dataclass(slots=True, frozen=True)
class DoctorCheck:
    """
    title: Single doctor check result.
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
class DoctorReport:
    """
    title: Doctor command report.
    attributes:
      checks:
        type: tuple[DoctorCheck, Ellipsis]
    """

    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        """
        title: Return overall doctor status.
        returns:
          type: bool
        """
        return all(check.ok for check in self.checks)


class DoctorService:
    """
    title: Environment and manifest diagnostics.
    attributes:
      _pixi:
        type: DoctorPixiAdapter
    """

    _pixi: DoctorPixiAdapter

    def __init__(self, pixi: DoctorPixiAdapter | None = None) -> None:
        self._pixi = pixi or PixiService()

    def run(self, directory: Path) -> DoctorReport:
        """
        title: Collect health checks for current project.
        parameters:
          directory:
            type: Path
        returns:
          type: DoctorReport
        """
        checks: list[DoctorCheck] = []

        pixi_ok = self._pixi.is_available()
        pixi_message = "pixi is available" if pixi_ok else "pixi is missing"
        checks.append(
            DoctorCheck(name="pixi", ok=pixi_ok, message=pixi_message)
        )

        arxproject_path = directory / MANIFEST_FILENAME
        arxproject_ok = arxproject_path.exists()
        arxproject_message = (
            f"{MANIFEST_FILENAME} found"
            if arxproject_ok
            else f"{MANIFEST_FILENAME} missing"
        )
        checks.append(
            DoctorCheck(
                name=MANIFEST_FILENAME,
                ok=arxproject_ok,
                message=arxproject_message,
            )
        )

        pixi_path = self._pixi.pixi_path(directory)
        pixi_file_ok = pixi_path.exists()
        pixi_file_message = (
            f"{PIXI_FILENAME} found"
            if pixi_file_ok
            else f"{PIXI_FILENAME} missing"
        )
        checks.append(
            DoctorCheck(
                name=PIXI_FILENAME,
                ok=pixi_file_ok,
                message=pixi_file_message,
            )
        )

        python_declared, pip_declared, clang_declared, detail = (
            self._dependency_checks(
                directory,
                pixi_file_ok,
            )
        )
        checks.append(
            DoctorCheck(
                name="python declared",
                ok=python_declared,
                message=detail["python"],
            )
        )
        checks.append(
            DoctorCheck(
                name="pip declared",
                ok=pip_declared,
                message=detail["pip"],
            )
        )
        checks.append(
            DoctorCheck(
                name="clang declared",
                ok=clang_declared,
                message=detail["clang"],
            )
        )

        return DoctorReport(checks=tuple(checks))

    def _dependency_checks(
        self,
        directory: Path,
        pixi_file_ok: bool,
    ) -> tuple[bool, bool, bool, dict[str, str]]:
        if not pixi_file_ok:
            details = {
                "python": f"{PIXI_FILENAME} missing",
                "pip": f"{PIXI_FILENAME} missing",
                "clang": f"{PIXI_FILENAME} missing",
            }
            return (False, False, False, details)

        try:
            dependencies = self._pixi.declared_dependencies(directory)
        except ManifestError as exc:
            details = {
                "python": str(exc),
                "pip": str(exc),
                "clang": str(exc),
            }
            return (False, False, False, details)

        python_ok = "python" in dependencies
        pip_ok = "pip" in dependencies
        clang_ok = "clang" in dependencies
        details = {
            "python": (
                "python is declared in pixi.toml"
                if python_ok
                else "python is not declared in pixi.toml"
            ),
            "pip": (
                "pip is declared in pixi.toml"
                if pip_ok
                else "pip is not declared in pixi.toml"
            ),
            "clang": (
                "clang is declared in pixi.toml"
                if clang_ok
                else "clang is not declared in pixi.toml"
            ),
        }
        return (python_ok, pip_ok, clang_ok, details)
