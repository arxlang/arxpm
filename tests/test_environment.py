"""
title: Tests for the environment abstraction and uv-backed implementations.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from arxpm.environment import (
    CondaEnvironment,
    ExistingVenvEnvironment,
    UvManagedEnvironment,
    build_environment,
    default_environment_config_from_cli,
)
from arxpm.errors import (
    EnvironmentError,
    ManifestError,
    MissingUvError,
)
from arxpm.external import CommandResult
from arxpm.models import EnvironmentConfig, Manifest, ProjectConfig


class Recorder:
    """
    title: Record external command invocations.
    attributes:
      calls:
        type: list[tuple[list[str], Path | None, bool]]
    """

    calls: list[tuple[list[str], Path | None, bool]]

    def __init__(self) -> None:
        self.calls = []

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        self.calls.append((list(command), cwd, check))
        return CommandResult(tuple(command), 0, "", "")


def _interpreter_name() -> str:
    return "python.exe" if sys.platform == "win32" else "python"


def _bin_dir() -> str:
    return "Scripts" if sys.platform == "win32" else "bin"


def test_uv_managed_environment_creates_venv(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    venv_dir = (tmp_path / ".venv").resolve()
    bin_dir = venv_dir / _bin_dir()

    def runner(
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        _ = cwd, check
        calls.append(list(command))
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / _interpreter_name()).write_text("", encoding="utf-8")
        return CommandResult(tuple(command), 0, "", "")

    env = UvManagedEnvironment(
        tmp_path,
        venv_path=".venv",
        runner=runner,
        which=lambda _: "/usr/bin/uv",
    )
    env.ensure_ready()

    assert (bin_dir / _interpreter_name()).exists()
    assert calls[0][:2] == ["uv", "venv"]


def test_uv_managed_environment_install_packages(tmp_path: Path) -> None:
    recorder = Recorder()
    env = UvManagedEnvironment(
        tmp_path,
        venv_path=".venv",
        runner=recorder,
        which=lambda _: "/usr/bin/uv",
    )

    env.install_packages(["pyyaml", "httpx"])

    assert recorder.calls[0][0][:3] == ["uv", "pip", "install"]
    assert "--python" in recorder.calls[0][0]
    assert "pyyaml" in recorder.calls[0][0]
    assert "httpx" in recorder.calls[0][0]


def test_uv_managed_environment_force_reinstall_and_no_deps(
    tmp_path: Path,
) -> None:
    recorder = Recorder()
    env = UvManagedEnvironment(
        tmp_path,
        venv_path=".venv",
        runner=recorder,
        which=lambda _: "/usr/bin/uv",
    )

    env.install_packages(
        ["/tmp/wheel.whl"],
        force_reinstall=True,
        no_deps=True,
    )

    cmd = recorder.calls[0][0]
    assert "--force-reinstall" in cmd
    assert "--no-deps" in cmd


def test_uv_managed_environment_requires_uv(tmp_path: Path) -> None:
    env = UvManagedEnvironment(
        tmp_path,
        runner=Recorder(),
        which=lambda _: None,
    )

    with pytest.raises(MissingUvError):
        env.ensure_ready()


def test_uv_managed_environment_empty_requirements_skips(
    tmp_path: Path,
) -> None:
    recorder = Recorder()
    env = UvManagedEnvironment(
        tmp_path,
        runner=recorder,
        which=lambda _: "/usr/bin/uv",
    )

    result = env.install_packages([])

    assert result.returncode == 0
    assert recorder.calls == []


def test_existing_venv_environment_validates_path(tmp_path: Path) -> None:
    venv_dir = tmp_path / "myenv"
    (venv_dir / _bin_dir()).mkdir(parents=True)
    (venv_dir / _bin_dir() / _interpreter_name()).write_text(
        "",
        encoding="utf-8",
    )

    env = ExistingVenvEnvironment(
        tmp_path,
        venv_path="myenv",
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )
    env.ensure_ready()

    assert env.python_executable() == (
        venv_dir / _bin_dir() / _interpreter_name()
    )


def test_existing_venv_environment_rejects_missing(tmp_path: Path) -> None:
    env = ExistingVenvEnvironment(
        tmp_path,
        venv_path="missing",
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )

    with pytest.raises(EnvironmentError):
        env.ensure_ready()


def test_conda_environment_resolves_by_name(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        _ = cwd, check
        calls.append(list(command))
        return CommandResult(
            tuple(command),
            0,
            "/fake/conda/envs/demo/bin/python\n",
            "",
        )

    env = CondaEnvironment(
        tmp_path,
        name="demo",
        runner=runner,
        which=lambda name: (
            "/usr/bin/conda" if name == "conda" else "/usr/bin/uv"
        ),
    )

    interpreter = env.python_executable()

    assert interpreter == Path("/fake/conda/envs/demo/bin/python")
    assert calls[0][:4] == ["conda", "run", "-n", "demo"]


def test_conda_environment_uses_path_when_provided(tmp_path: Path) -> None:
    env_path = tmp_path / "envs" / "demo"
    (env_path / _bin_dir()).mkdir(parents=True)

    env = CondaEnvironment(
        tmp_path,
        path=str(env_path),
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )

    interpreter = env.python_executable()

    assert interpreter == env_path / _bin_dir() / _interpreter_name()


def test_conda_environment_requires_name_or_path(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentError):
        CondaEnvironment(
            tmp_path,
            runner=Recorder(),
            which=lambda _: "/usr/bin/uv",
        )


def _manifest_with_environment(config: EnvironmentConfig) -> Manifest:
    return Manifest(
        project=ProjectConfig(name="demo"),
        environment=config,
    )


def test_build_environment_dispatches_to_managed_venv(tmp_path: Path) -> None:
    manifest = _manifest_with_environment(EnvironmentConfig.default())
    env = build_environment(
        manifest,
        tmp_path,
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )

    assert isinstance(env, UvManagedEnvironment)


def test_build_environment_dispatches_to_existing_venv(tmp_path: Path) -> None:
    manifest = _manifest_with_environment(
        EnvironmentConfig(kind="existing-venv", path="/some/venv"),
    )
    env = build_environment(
        manifest,
        tmp_path,
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )

    assert isinstance(env, ExistingVenvEnvironment)


def test_build_environment_dispatches_to_conda(tmp_path: Path) -> None:
    manifest = _manifest_with_environment(
        EnvironmentConfig(kind="conda", name="demo"),
    )
    env = build_environment(
        manifest,
        tmp_path,
        runner=Recorder(),
        which=lambda _: "/usr/bin/uv",
    )

    assert isinstance(env, CondaEnvironment)


def test_default_environment_config_from_cli_returns_default_when_empty() -> (
    None
):
    config = default_environment_config_from_cli(None, None, None)
    assert config.is_default()


def test_default_environment_config_from_cli_builds_existing_venv() -> None:
    config = default_environment_config_from_cli(
        "existing-venv",
        "/tmp/env",
        None,
    )
    assert config.kind == "existing-venv"
    assert config.path == "/tmp/env"


def test_default_environment_config_from_cli_rejects_unknown_kind() -> None:
    with pytest.raises(ManifestError):
        default_environment_config_from_cli("bogus", None, None)
