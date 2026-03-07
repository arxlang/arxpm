"""Tests for doctor checks."""

from __future__ import annotations

from pathlib import Path

from arxpm.doctor import DoctorService
from arxpm.errors import ExternalCommandError
from arxpm.external import CommandResult
from arxpm.manifest import create_default_manifest, save_manifest


class FakePixiService:
    """Pixi test double for doctor."""

    def __init__(self, available: bool, runnable: set[str]) -> None:
        self._available = available
        self._runnable = runnable

    def is_available(self) -> bool:
        return self._available

    def run(self, directory: Path, args: list[str]) -> CommandResult:
        tool = args[0]
        if tool in self._runnable:
            return CommandResult(("pixi", "run", *args), 0, "", "")
        raise ExternalCommandError(("pixi", "run", *args), 1, "not found")


def test_doctor_ok_with_tools_on_path(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))

    def which(name: str) -> str | None:
        if name in {"arx", "clang"}:
            return f"/usr/bin/{name}"
        return None

    service = DoctorService(
        pixi=FakePixiService(available=True, runnable=set()),
        which=which,
    )

    report = service.run(tmp_path)

    assert report.ok is True


def test_doctor_uses_pixi_for_tools_when_not_on_path(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    service = DoctorService(
        pixi=FakePixiService(available=True, runnable={"arx", "clang"}),
        which=lambda _: None,
    )

    report = service.run(tmp_path)

    checks = {check.name: check for check in report.checks}
    assert checks["arx"].ok is True
    assert checks["clang"].ok is True


def test_doctor_reports_invalid_manifest(tmp_path: Path) -> None:
    (tmp_path / "arxproj.toml").write_text("[project]\n", encoding="utf-8")
    service = DoctorService(
        pixi=FakePixiService(available=False, runnable=set()),
        which=lambda _: None,
    )

    report = service.run(tmp_path)

    checks = {check.name: check for check in report.checks}
    assert checks["manifest"].ok is False
