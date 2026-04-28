"""
title: Tests for healthcheck service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from arxpm.environment import EnvironmentFactory, EnvironmentRuntime
from arxpm.errors import EnvironmentError
from arxpm.external import CommandResult
from arxpm.healthcheck import HealthCheckService
from arxpm.manifest import (
    create_default_manifest,
    load_manifest,
    save_manifest,
)
from arxpm.models import BuildConfig, EnvironmentConfig, Manifest
from arxpm.project import ProjectService


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


class StubRunner:
    """
    title: Command runner stub for compiler import checks.
    attributes:
      returncode:
        type: int
    """

    returncode: int

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        _ = cwd, check, env
        return CommandResult(tuple(command), self.returncode, "", "")


def _stub_factory(description: str, fail: bool = False) -> EnvironmentFactory:
    def _build(manifest: Manifest, project_dir: Path) -> EnvironmentRuntime:
        _ = manifest, project_dir
        return StubEnvironment(description, fail=fail)

    return _build


def _which_all(tool: str) -> str | None:
    return f"/usr/bin/{tool}"


def _project_service() -> ProjectService:
    return ProjectService(environment_factory=_stub_factory("venv"))


def test_healthcheck_reports_success(tmp_path: Path) -> None:
    _project_service().init(tmp_path, name="demo")
    service = HealthCheckService(
        environment_factory=_stub_factory("venv at /tmp/.venv"),
        which=_which_all,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is True
    assert checks[".arxproject.toml"].ok is True
    assert checks["manifest parsing"].ok is True
    assert checks["package name"].ok is True
    assert checks["source root"].ok is True
    assert checks["package root"].ok is True
    assert checks["__init__.x"].ok is True
    assert checks["main.x"].ok is True
    assert checks["uv"].ok is True
    assert checks["compiler (python -m arx)"].ok is True
    assert checks["environment"].ok is True
    assert "reachable" in checks["environment"].message


def test_healthcheck_reports_missing_manifest(tmp_path: Path) -> None:
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks[".arxproject.toml"].ok is False
    assert checks["manifest parsing"].ok is False


def test_healthcheck_reports_missing_source_root(tmp_path: Path) -> None:
    manifest = create_default_manifest("demo")
    manifest.build = BuildConfig(
        src_dir=manifest.build.src_dir,
        out_dir=manifest.build.out_dir,
        package=manifest.build.package,
        mode="app",
    )
    save_manifest(tmp_path, manifest)
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["source root"].ok is False
    assert "source root not found" in checks["source root"].message


def test_healthcheck_reports_missing_uv(tmp_path: Path) -> None:
    _project_service().init(tmp_path, name="demo")

    def _which(tool: str) -> str | None:
        if tool == "uv":
            return None
        return f"/usr/bin/{tool}"

    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["uv"].ok is False


def test_healthcheck_reports_missing_environment_compiler(
    tmp_path: Path,
) -> None:
    _project_service().init(tmp_path, name="demo")
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
        runner=StubRunner(returncode=1),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert checks["compiler (python -m arx)"].ok is False


def test_healthcheck_reports_missing_custom_compiler(tmp_path: Path) -> None:
    _project_service().init(tmp_path, name="demo")
    manifest = load_manifest(tmp_path)
    manifest.toolchain = type(manifest.toolchain)(
        compiler="custom-arx",
        linker=manifest.toolchain.linker,
    )
    save_manifest(tmp_path, manifest)

    def _which(tool: str) -> str | None:
        if tool == "custom-arx":
            return None
        return f"/usr/bin/{tool}"

    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert checks["compiler (custom-arx)"].ok is False


def test_healthcheck_reports_unreachable_environment(
    tmp_path: Path,
) -> None:
    _project_service().init(tmp_path, name="demo")
    service = HealthCheckService(
        environment_factory=_stub_factory("venv", fail=True),
        which=_which_all,
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert report.ok is False
    assert checks["environment"].ok is False
    assert "environment not reachable" in checks["environment"].message


def test_healthcheck_reports_invalid_package_name(tmp_path: Path) -> None:
    manifest = create_default_manifest("my-project")
    manifest.build = BuildConfig(
        src_dir=manifest.build.src_dir,
        out_dir=manifest.build.out_dir,
        package=manifest.build.package,
        mode="app",
    )
    save_manifest(tmp_path, manifest)
    service = HealthCheckService(
        environment_factory=_stub_factory("venv"),
        which=_which_all,
        runner=StubRunner(),
    )

    report = service.run(tmp_path)
    checks = {check.name: check for check in report.checks}

    assert checks["package name"].ok is False
    assert "set [build].package explicitly" in checks["package name"].message


def test_healthcheck_reports_broken_venv(tmp_path: Path) -> None:
    service = _project_service()
    service.init(tmp_path, name="demo")
    manifest = create_default_manifest("demo")
    broken = tmp_path / "broken-venv"
    broken.mkdir()
    manifest_with_env = Manifest(
        project=manifest.project,
        build=load_manifest(tmp_path).build,
        dependencies=manifest.dependencies,
        toolchain=manifest.toolchain,
        environment=EnvironmentConfig(
            kind="venv",
            path=str(broken),
        ),
    )
    save_manifest(tmp_path, manifest_with_env)
    report = HealthCheckService(which=_which_all).run(tmp_path)
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
