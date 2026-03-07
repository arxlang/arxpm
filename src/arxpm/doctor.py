"""Environment health checks for arxpm."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arxpm.errors import ManifestError
from arxpm.manifest import MANIFEST_FILENAME
from arxpm.pixi import PIXI_FILENAME, PixiService


class DoctorPixiAdapter(Protocol):
    """Doctor-level pixi adapter protocol."""

    def is_available(self) -> bool:
        """Return whether pixi is available."""

    def pixi_path(self, directory: Path) -> Path:
        """Return pixi.toml path."""

    def declared_dependencies(self, directory: Path) -> set[str]:
        """Return declared dependencies from pixi.toml."""


@dataclass(slots=True, frozen=True)
class DoctorCheck:
    """Single doctor check result."""

    name: str
    ok: bool
    message: str


@dataclass(slots=True, frozen=True)
class DoctorReport:
    """Doctor command report."""

    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        """Return overall doctor status."""
        return all(check.ok for check in self.checks)


class DoctorService:
    """Environment and manifest diagnostics."""

    def __init__(self, pixi: DoctorPixiAdapter | None = None) -> None:
        self._pixi = pixi or PixiService()

    def run(self, directory: Path) -> DoctorReport:
        """Collect health checks for current project."""
        checks: list[DoctorCheck] = []

        pixi_ok = self._pixi.is_available()
        pixi_message = "pixi is available" if pixi_ok else "pixi is missing"
        checks.append(
            DoctorCheck(name="pixi", ok=pixi_ok, message=pixi_message)
        )

        arxproj_path = directory / MANIFEST_FILENAME
        arxproj_ok = arxproj_path.exists()
        arxproj_message = (
            f"{MANIFEST_FILENAME} found"
            if arxproj_ok
            else f"{MANIFEST_FILENAME} missing"
        )
        checks.append(
            DoctorCheck(
                name=MANIFEST_FILENAME,
                ok=arxproj_ok,
                message=arxproj_message,
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

        python_declared, clang_declared, detail = self._dependency_checks(
            directory,
            pixi_file_ok,
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
    ) -> tuple[bool, bool, dict[str, str]]:
        if not pixi_file_ok:
            details = {
                "python": f"{PIXI_FILENAME} missing",
                "clang": f"{PIXI_FILENAME} missing",
            }
            return (False, False, details)

        try:
            dependencies = self._pixi.declared_dependencies(directory)
        except ManifestError as exc:
            details = {
                "python": str(exc),
                "clang": str(exc),
            }
            return (False, False, details)

        python_ok = "python" in dependencies
        clang_ok = "clang" in dependencies
        details = {
            "python": (
                "python is declared in pixi.toml"
                if python_ok
                else "python is not declared in pixi.toml"
            ),
            "clang": (
                "clang is declared in pixi.toml"
                if clang_ok
                else "clang is not declared in pixi.toml"
            ),
        }
        return (python_ok, clang_ok, details)
