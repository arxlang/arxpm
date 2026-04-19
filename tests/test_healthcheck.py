"""
title: Tests for healthcheck service.
"""

from __future__ import annotations

from pathlib import Path

from arxpm.environment import EnvironmentFactory, EnvironmentRuntime
from arxpm.errors import EnvironmentError
from arxpm.external import CommandResult
from arxpm.healthcheck import HealthCheckService
from arxpm.manifest import create_default_manifest, save_manifest
from arxpm.models import EnvironmentConfig, Manifest


class StubEnvironment:
    """
    title: Environment runtime stub for healthcheck tests.
    attributes:
      _description:
        type: str
      _fail:
        type: bool
    """

    _description: str
    _fail: bool

    def __init__(self, description: str, fail: bool = False) -> None:
        self._description = description
        self._fail = fail

    def ensure_ready(self) -> None:
        if self._fail:
            raise EnvironmentError("cannot create env")

    def validate(self) -> None:
        if self._fail:
            raise EnvironmentError("environment not reachable")

    def python_executable(self) -> Path:
        return Path("/fake/python")

    def install_packages(
        self,
        requirements: object,
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        _ = requirements, force_reinstall, no_deps
        return CommandResult(("uv", "pip", "install"), 0, "", "")

    def describe(self) -> str:
        return self._description


def _stub_factory(description: str, fail: bool = False) -> EnvironmentFactory:
    def _build(manifest: Manifest, project_dir: Path) -> EnvironmentRuntime:
        _ = manifest, project_dir
        return StubEnvironment(description, fail=fail)

    return _build


def _which_all(tool: str) -> str | None:
    return f"/usr/bin/{tool}"


def _which_none(tool: str) -> str | None:
    _ = tool
    return None


def test_healthcheck_reports_success(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    service = HealthCheckService(
        environment_factory=_stub_factory("venv at /tmp/.venv"),
        which=_which_all,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is True
    assert checks[".arxproject.toml"].ok is True
    assert checks["manifest parsing"].ok is True
    assert checks["uv"].ok is True
    assert checks["compiler (arx)"].ok is True
    assert checks["environment"].ok is True
    assert "reachable" in checks["environment"].message


def test_healthcheck_reports_missing_manifest(tmp_path: Path) -> None:
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks[".arxproject.toml"].ok is False
    assert checks["manifest parsing"].ok is False


def test_healthcheck_reports_missing_uv(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))

    def _which(tool: str) -> str | None:
        if tool == "uv":
            return None
        return f"/usr/bin/{tool}"

    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["uv"].ok is False


def test_healthcheck_reports_missing_compiler(tmp_path: Path) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))

    def _which(tool: str) -> str | None:
        if tool == "arx":
            return None
        return f"/usr/bin/{tool}"

    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert checks["compiler (arx)"].ok is False


def test_healthcheck_reports_unreachable_environment(
    tmp_path: Path,
) -> None:
    save_manifest(tmp_path, create_default_manifest("demo"))
    service = HealthCheckService(
        environment_factory=_stub_factory("venv", fail=True),
        which=_which_all,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["environment"].ok is False
    assert "environment not reachable" in checks["environment"].message


def test_healthcheck_reports_broken_venv(tmp_path: Path) -> None:
    manifest = create_default_manifest("demo")
    broken = tmp_path / "broken-venv"
    broken.mkdir()
    manifest_with_env = Manifest(
        project=manifest.project,
        build=manifest.build,
        dependencies=manifest.dependencies,
        toolchain=manifest.toolchain,
        environment=EnvironmentConfig(
            kind="venv",
            path=str(broken),
        ),
    )
    save_manifest(tmp_path, manifest_with_env)
    service = HealthCheckService(which=_which_all)

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["environment"].ok is False
    assert "venv" in checks["environment"].message


def test_healthcheck_reports_manifest_parse_failure(tmp_path: Path) -> None:
    (tmp_path / ".arxproject.toml").write_text(
        '[project]\nname = "demo"\n',
        encoding="utf-8",
    )
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks[".arxproject.toml"].ok is True
    assert checks["manifest parsing"].ok is False
    assert "version" in checks["manifest parsing"].message
