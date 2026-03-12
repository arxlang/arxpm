"""
title: Tests for doctor checks.
"""

from __future__ import annotations

from pathlib import Path

from arxpm.doctor import DoctorService
from arxpm.errors import ManifestError
from arxpm.manifest import create_default_manifest, save_manifest


class FakePixiService:
    """
    title: Pixi test double for doctor.
    attributes:
      _available:
        type: bool
      _dependencies:
        type: set[str]
      _invalid:
        type: bool
    """

    _available: bool
    _dependencies: set[str]
    _invalid: bool

    def __init__(
        self,
        available: bool,
        dependencies: set[str] | None = None,
        invalid: bool = False,
    ) -> None:
        self._available = available
        self._dependencies = dependencies or set()
        self._invalid = invalid

    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def pixi_path(directory: Path) -> Path:
        return directory / "pixi.toml"

    def declared_dependencies(self, directory: Path) -> set[str]:
        if self._invalid:
            raise ManifestError("invalid TOML in pixi.toml")
        return set(self._dependencies)


def test_doctor_reports_requested_health_checks(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    (tmp_path / "pixi.toml").write_text("[dependencies]\n", encoding="utf-8")
    service = DoctorService(
        pixi=FakePixiService(
            available=True,
            dependencies={"python", "pip", "clang"},
        ),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert checks["pixi"].ok is True
    assert checks["arxproj.toml"].ok is True
    assert checks["pixi.toml"].ok is True
    assert checks["python declared"].ok is True
    assert checks["pip declared"].ok is True
    assert checks["clang declared"].ok is True


def test_doctor_reports_missing_pixi_manifest(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    service = DoctorService(
        pixi=FakePixiService(
            available=True,
            dependencies={"python", "pip", "clang"},
        ),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}
    assert checks["pixi.toml"].ok is False
    assert checks["python declared"].ok is False
    assert checks["pip declared"].ok is False
    assert checks["clang declared"].ok is False


def test_doctor_reports_invalid_pixi_file(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    (tmp_path / "pixi.toml").write_text("[dependencies]\n", encoding="utf-8")
    service = DoctorService(
        pixi=FakePixiService(available=True, invalid=True),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}
    assert checks["python declared"].ok is False
    assert checks["pip declared"].ok is False
    assert checks["clang declared"].ok is False
