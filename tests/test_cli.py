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
from arxpm.errors import MissingUvError
from arxpm.healthcheck import HealthCheck, HealthReport

runner = CliRunner()


class FailingInstallProjectService:
    """
    title: Project service that fails on install.
    """

    def install(self, directory: Path, dev: bool = False) -> None:
        _ = directory, dev
        raise MissingUvError("uv is missing")


class PassingHealthcheckService:
    """
    title: Healthcheck service that always succeeds.
    """

    def run(self, directory: Path) -> HealthReport:
        _ = directory
        return HealthReport(checks=(HealthCheck("uv", True, "ok"),))


class FailingHealthcheckService:
    """
    title: Healthcheck service with a failing check.
    """

    def run(self, directory: Path) -> HealthReport:
        _ = directory
        return HealthReport(checks=(HealthCheck("uv", False, "missing"),))


class PassingRunProjectService:
    """
    title: Project service that always succeeds on run.
    """

    def run(self, directory: Path) -> None:
        _ = directory
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
        _ = repository_url, skip_existing, dry_run
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

    result = runner.invoke(app, ["init", "--name", "hello-arx"])

    assert result.exit_code == 0
    manifest_path = tmp_path / ".arxproject.toml"
    assert manifest_path.exists()

    manifest_data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    src_dir = manifest_data["build"]["src_dir"]
    entry = manifest_data["build"]["entry"]
    assert isinstance(src_dir, str)
    assert isinstance(entry, str)
    assert (tmp_path / src_dir / entry).exists()
    assert "environment" not in manifest_data


def test_init_command_writes_custom_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "init",
            "--name",
            "demo",
            "--env-kind",
            "venv",
            "--env-path",
            "/tmp/demo-env",
        ],
    )

    assert result.exit_code == 0
    manifest_data = tomllib.loads(
        (tmp_path / ".arxproject.toml").read_text(encoding="utf-8"),
    )
    assert manifest_data["environment"]["kind"] == "venv"
    assert manifest_data["environment"]["path"] == "/tmp/demo-env"


def test_add_command_writes_registry_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "demo"])

    result = runner.invoke(app, ["add", "http"])

    assert result.exit_code == 0
    manifest = (tmp_path / ".arxproject.toml").read_text(encoding="utf-8")
    assert '"http",' in manifest
    assert "[dependencies]" not in manifest


def test_install_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        FailingInstallProjectService,
    )

    result = runner.invoke(app, ["install"])

    assert result.exit_code == 1
    assert "uv is missing" in result.output


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


def test_healthcheck_command_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.HealthCheckService",
        PassingHealthcheckService,
    )

    result = runner.invoke(app, ["healthcheck"])

    assert result.exit_code == 0
    assert "[ok] uv: ok" in result.output


def test_healthcheck_command_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.HealthCheckService",
        FailingHealthcheckService,
    )

    result = runner.invoke(app, ["healthcheck"])

    assert result.exit_code == 1
    assert "[fail] uv: missing" in result.output


def test_doctor_command_is_removed() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
