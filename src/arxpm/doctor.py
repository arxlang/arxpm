"""Environment health checks for arxpm."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shutil

from arxpm.errors import ArxpmError, ManifestError
from arxpm.manifest import load_manifest
from arxpm.pixi import PixiService


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

    def __init__(
        self,
        pixi: PixiService | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._pixi = pixi or PixiService()
        self._which = which

    def run(self, directory: Path) -> DoctorReport:
        """Collect health checks for current project."""
        checks: list[DoctorCheck] = []

        pixi_ok = self._pixi.is_available()
        pixi_message = (
            "pixi is available"
            if pixi_ok
            else "pixi is not available on PATH"
        )
        checks.append(
            DoctorCheck(name="pixi", ok=pixi_ok, message=pixi_message)
        )

        try:
            load_manifest(directory)
        except ManifestError as exc:
            checks.append(
                DoctorCheck(
                    name="manifest",
                    ok=False,
                    message=str(exc),
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name="manifest",
                    ok=True,
                    message="arxproj.toml is valid",
                )
            )

        checks.append(self._check_tool("arx", directory, pixi_ok))
        checks.append(self._check_tool("clang", directory, pixi_ok))

        return DoctorReport(checks=tuple(checks))

    def _check_tool(
        self,
        tool: str,
        directory: Path,
        pixi_ok: bool,
    ) -> DoctorCheck:
        path = self._which(tool)
        if path is not None:
            return DoctorCheck(
                name=tool,
                ok=True,
                message=f"{tool} is available at {path}",
            )

        if pixi_ok:
            try:
                self._pixi.run(directory, [tool, "--version"])
            except ArxpmError:
                pass
            else:
                return DoctorCheck(
                    name=tool,
                    ok=True,
                    message=f"{tool} is available via pixi",
                )

        return DoctorCheck(
            name=tool,
            ok=False,
            message=f"{tool} is not available",
        )
