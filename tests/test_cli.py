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

    def install(
        self,
        directory: Path,
        groups: tuple[str, ...] | list[str] = (),
        dev: bool = False,
    ) -> None:
        _ = directory, groups, dev
        raise MissingUvError("uv is missing")


class FailingProjectService:
    """
    title: Project service that fails every workflow.
    """

    def init(
        self,
        directory: Path,
        name: str | None = None,
        environment: object | None = None,
    ) -> None:
        _ = directory, name, environment
        raise MissingUvError("workflow failed")

    def add_dependency(
        self,
        directory: Path,
        name: str,
        path: Path | None = None,
        git: str | None = None,
    ) -> None:
        _ = directory, name, path, git
        raise MissingUvError("workflow failed")

    def build(self, directory: Path) -> None:
        _ = directory
        raise MissingUvError("workflow failed")

    def run(self, directory: Path) -> None:
        _ = directory
        raise MissingUvError("workflow failed")

    def pack(self, directory: Path) -> None:
        _ = directory
        raise MissingUvError("workflow failed")

    def publish(
        self,
        directory: Path,
        repository_url: str | None = None,
        skip_existing: bool = False,
        dry_run: bool = False,
    ) -> None:
        _ = directory, repository_url, skip_existing, dry_run
        raise MissingUvError("workflow failed")


class CapturingInstallProjectService:
    """
    title: Project service that records install flags.
    attributes:
      last_groups:
        type: tuple[str, Ellipsis]
    """

    last_groups: tuple[str, ...] = ()

    def install(
        self,
        directory: Path,
        groups: tuple[str, ...] | list[str] = (),
        dev: bool = False,
    ) -> None:
        _ = directory, dev
        type(self).last_groups = tuple(groups)


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


class CapturingCredentialStore:
    """
    title: Credential store that records config command calls.
    attributes:
      set_calls:
        type: list[tuple[str, str]]
      delete_calls:
        type: list[str]
    """

    set_calls: list[tuple[str, str]] = []
    delete_calls: list[str] = []

    def ensure_available(self) -> None:
        pass

    def set_token_key(self, key: str, token: str) -> str:
        type(self).set_calls.append((key, token))
        return key.rsplit(".", maxsplit=1)[-1]

    def delete_token_key(self, key: str) -> str:
        type(self).delete_calls.append(key)
        return key.rsplit(".", maxsplit=1)[-1]


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
    build = manifest_data["build"]
    src_dir = build["src_dir"]
    package = build["package"]
    assert build["mode"] == "app"
    assert isinstance(src_dir, str)
    assert isinstance(package, str)
    assert (tmp_path / src_dir / package / "__init__.x").exists()
    assert (tmp_path / src_dir / package / "main.x").exists()
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


def test_init_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


def test_config_command_stores_token_in_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    CapturingCredentialStore.set_calls = []
    CapturingCredentialStore.delete_calls = []
    monkeypatch.setattr(
        "arxpm.cli.PublishCredentialStore",
        CapturingCredentialStore,
    )

    result = runner.invoke(
        app,
        ["config", "pypi-token.pypi"],
        input="pypi-token\npypi-token\n",
    )

    assert result.exit_code == 0
    assert CapturingCredentialStore.set_calls == [
        ("pypi-token.pypi", "pypi-token")
    ]
    assert "Stored publish token for pypi" in result.output
    assert "pypi-token\n" not in result.output


def test_config_command_removes_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    CapturingCredentialStore.set_calls = []
    CapturingCredentialStore.delete_calls = []
    monkeypatch.setattr(
        "arxpm.cli.PublishCredentialStore",
        CapturingCredentialStore,
    )

    result = runner.invoke(app, ["config", "--unset", "pypi-token.pypi"])

    assert result.exit_code == 0
    assert CapturingCredentialStore.delete_calls == ["pypi-token.pypi"]
    assert "Removed publish token for pypi" in result.output


def test_config_command_reports_missing_keyring_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.credentials._keyring", None)

    result = runner.invoke(app, ["config", "pypi-token.pypi"])

    assert result.exit_code == 1
    assert "keyring package is not available" in result.output
    assert "ARXPM_PUBLISH_TOKEN" in result.output


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


def test_add_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["add", "http"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


def test_install_command_passes_selected_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        CapturingInstallProjectService,
    )

    result = runner.invoke(
        app,
        ["install", "--group", "dev,docs", "--group", "lint", "--dev"],
    )

    assert result.exit_code == 0
    assert CapturingInstallProjectService.last_groups == (
        "dev",
        "docs",
        "lint",
        "dev",
    )


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


def test_build_command_reports_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingBuildProjectService,
    )

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 0
    assert "Build completed." in result.output


def test_build_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


def test_run_command_omits_completion_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingRunProjectService,
    )

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0


def test_run_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


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


def test_pack_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["pack"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


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


def test_publish_command_reports_published_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "arxpm.cli.ProjectService",
        PassingPublishProjectService,
    )

    result = runner.invoke(app, ["publish"])

    assert result.exit_code == 0
    assert "Published artifacts:" in result.output
    assert "demo-0.1.0-py3-none-any.whl" in result.output


def test_publish_command_surfaces_human_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.cli.ProjectService", FailingProjectService)

    result = runner.invoke(app, ["publish"])

    assert result.exit_code == 1
    assert "workflow failed" in result.output


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


def test_doctor_command_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.cli.HealthCheckService",
        PassingHealthcheckService,
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "[ok] uv: ok" in result.output
