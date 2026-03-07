"""Tests for Typer CLI behavior."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from arxpm.cli import app
from arxpm.doctor import DoctorCheck, DoctorReport
from arxpm.errors import MissingPixiError

runner = CliRunner()


class FailingInstallProjectService:
    """Project service that fails on install."""

    def install(self, directory: Path) -> None:
        raise MissingPixiError("pixi is missing")


class PassingDoctorService:
    """Doctor service that always succeeds."""

    def run(self, directory: Path) -> DoctorReport:
        return DoctorReport(checks=(DoctorCheck("pixi", True, "ok"),))


def test_init_command_creates_project_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--name", "hello-arx", "--no-pixi"])

    assert result.exit_code == 0
    assert (tmp_path / "arxproj.toml").exists()
    assert (tmp_path / "src" / "main.arx").exists()


def test_add_command_writes_registry_dependency(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo", "--no-pixi"])

    result = runner.invoke(app, ["add", "http"])

    assert result.exit_code == 0
    manifest = (tmp_path / "arxproj.toml").read_text(encoding="utf-8")
    assert '"http" = { source = "registry" }' in manifest


def test_install_command_surfaces_human_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        FailingInstallProjectService,
    )

    result = runner.invoke(app, ["install"])

    assert result.exit_code == 1
    assert "pixi is missing" in result.output


def test_install_command_requires_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 1
    assert "manifest not found" in result.output


def test_doctor_command_reports_success(monkeypatch) -> None:
    monkeypatch.setattr("arxpm.cli.DoctorService", PassingDoctorService)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "[ok] pixi: ok" in result.output
