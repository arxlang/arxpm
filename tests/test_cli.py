"""
title: Tests for Typer CLI behavior.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from arxpm._toml import tomllib
from arxpm.cli import app
from arxpm.doctor import DoctorCheck, DoctorReport
from arxpm.errors import MissingPixiError

runner = CliRunner()


class FailingInstallProjectService:
    """
    title: Project service that fails on install.
    """

    def install(self, directory: Path) -> None:
        raise MissingPixiError("pixi is missing")


class PassingDoctorService:
    """
    title: Doctor service that always succeeds.
    """

    def run(self, directory: Path) -> DoctorReport:
        return DoctorReport(checks=(DoctorCheck("pixi", True, "ok"),))


class PassingRunProjectService:
    """
    title: Project service that always succeeds on run.
    """

    def run(self, directory: Path) -> None:
        return None


class PassingBuildProjectService:
    """
    title: Project service that always succeeds on build.
    """

    def build(self, directory: Path) -> SimpleNamespace:
        return SimpleNamespace(artifact=directory / "build" / "demo")


class PassingPublishProjectService:
    """
    title: Project service that always succeeds on publish/pack.
    """

    def pack(self, directory: Path) -> SimpleNamespace:
        return SimpleNamespace(
            artifacts=(
                directory / "dist" / "demo-0.1.0-py3-none-any.whl",
                directory / "dist" / "demo-0.1.0.tar.gz",
            )
        )

    def publish(
        self,
        directory: Path,
        repository_url: str | None = None,
        skip_existing: bool = False,
        dry_run: bool = False,
    ) -> SimpleNamespace:
        _ = repository_url
        _ = skip_existing
        _ = dry_run
        return SimpleNamespace(
            artifacts=(
                directory / "dist" / "demo-0.1.0-py3-none-any.whl",
                directory / "dist" / "demo-0.1.0.tar.gz",
            )
        )


def test_init_command_creates_project_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--name", "hello-arx", "--no-pixi"])

    assert result.exit_code == 0
    manifest_path = tmp_path / "arxproj.toml"
    assert manifest_path.exists()

    manifest_data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest_data["build"]["entry"]
    assert isinstance(entry, str)
    assert (tmp_path / entry).exists()


def test_add_command_writes_registry_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo", "--no-pixi"])

    result = runner.invoke(app, ["add", "http"])

    assert result.exit_code == 0
    manifest = (tmp_path / "arxproj.toml").read_text(encoding="utf-8")
    assert '"http" = { source = "registry" }' in manifest


def test_install_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        FailingInstallProjectService,
    )

    result = runner.invoke(app, ["install"])

    assert result.exit_code == 1
    assert "pixi is missing" in result.output


def test_install_command_requires_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 1
    assert "manifest not found" in result.output


def test_compile_command_reports_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingBuildProjectService,
    )

    result = runner.invoke(app, ["compile"])

    assert result.exit_code == 0
    assert "Compile completed." in result.output


def test_run_command_omits_completion_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingRunProjectService,
    )

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0


def test_pack_command_reports_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingPublishProjectService,
    )

    result = runner.invoke(app, ["pack"])

    assert result.exit_code == 0
    assert "Pack completed." in result.output
    assert "demo-0.1.0-py3-none-any.whl" in result.output


def test_publish_command_reports_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingPublishProjectService,
    )

    result = runner.invoke(
        app,
        [
            "publish",
            "--dry-run",
            "--repository-url",
            "https://test.pypi.org/legacy/",
            "--skip-existing",
        ],
    )

    assert result.exit_code == 0
    assert "Publish dry-run completed." in result.output
    assert "demo-0.1.0-py3-none-any.whl" in result.output


def test_doctor_command_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.DoctorService", PassingDoctorService)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "[ok] pixi: ok" in result.output
