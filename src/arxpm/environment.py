"""
title: Environment runtime abstraction and uv-backed implementations.
"""

from __future__ import annotations

import shutil
import sys
import sysconfig
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from arxpm.errors import (
    EnvironmentError,
    ManifestError,
    MissingUvError,
)
from arxpm.external import CommandResult, CommandRunner, run_command
from arxpm.models import DEFAULT_VENV_PATH, EnvironmentConfig, Manifest

WhichFn = Callable[[str], str | None]


class EnvironmentRuntime(Protocol):
    """
    title: Backend-neutral Python environment interface.
    """

    def ensure_ready(self) -> None:
        """
        title: Create the environment if needed, or validate it otherwise.
        """

    def validate(self) -> None:
        """
        title: Non-mutating check that the environment is reachable.
        raises:
          EnvironmentError: when the environment cannot be reached.
        """

    def python_executable(self) -> Path:
        """
        title: Return path to the environment's python interpreter.
        returns:
          type: Path
        """

    def install_packages(
        self,
        requirements: Sequence[str],
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        """
        title: Install packages into the environment via uv.
        parameters:
          requirements:
            type: Sequence[str]
          force_reinstall:
            type: bool
          no_deps:
            type: bool
        returns:
          type: CommandResult
        """

    def executable(self, name: str) -> Path:
        """
        title: Return an executable installed in this environment.
        parameters:
          name:
            type: str
        returns:
          type: Path
        """

    def describe(self) -> str:
        """
        title: Human-readable description of the environment.
        returns:
          type: str
        """


def environment_executable(
    environment: EnvironmentRuntime,
    executable: str,
) -> Path:
    """
    title: Return an executable installed beside the environment interpreter.
    parameters:
      environment:
        type: EnvironmentRuntime
      executable:
        type: str
    returns:
      type: Path
    """
    return environment.executable(executable)


class _UvBackend:
    """
    title: Shared uv-backed install logic used by concrete backends.
    attributes:
      _project_dir:
        type: Path
      _runner:
        type: CommandRunner
      _which:
        type: WhichFn
    """

    _project_dir: Path
    _runner: CommandRunner
    _which: WhichFn

    def __init__(
        self,
        project_dir: Path,
        runner: CommandRunner = run_command,
        which: WhichFn = shutil.which,
    ) -> None:
        self._project_dir = project_dir
        self._runner = runner
        self._which = which

    def _ensure_uv(self) -> None:
        if self._which("uv") is None:
            raise MissingUvError(
                "uv is required but was not found on PATH "
                "(install with `pip install uv`)"
            )

    def _install_with_uv(
        self,
        interpreter: Path,
        requirements: Sequence[str],
        *,
        force_reinstall: bool,
        no_deps: bool,
    ) -> CommandResult:
        self._ensure_uv()
        reqs = [r for r in requirements if r]
        if not reqs:
            return CommandResult(
                ("uv", "pip", "install"),
                0,
                "",
                "",
            )
        command = [
            "uv",
            "pip",
            "install",
            "--python",
            str(interpreter),
        ]
        if force_reinstall:
            command.append("--force-reinstall")
        if no_deps:
            command.append("--no-deps")
        command.extend(reqs)
        return self._runner(
            command,
            cwd=self._project_dir,
            check=True,
        )


class UvManagedEnvironment(_UvBackend):
    """
    title: uv-backed virtual environment managed by arxpm.
    attributes:
      _project_dir:
        type: Path
      _runner:
        type: CommandRunner
      _which:
        type: WhichFn
      _venv_path:
        type: Path
    """

    _venv_path: Path

    def __init__(
        self,
        project_dir: Path,
        venv_path: str = DEFAULT_VENV_PATH,
        runner: CommandRunner = run_command,
        which: WhichFn = shutil.which,
    ) -> None:
        super().__init__(project_dir, runner=runner, which=which)
        self._venv_path = _resolve_venv_path(project_dir, venv_path)

    def ensure_ready(self) -> None:
        self._ensure_uv()
        interpreter = _interpreter_for(self._venv_path)
        if interpreter.exists():
            return
        self._venv_path.parent.mkdir(parents=True, exist_ok=True)
        self._runner(
            ["uv", "venv", str(self._venv_path)],
            cwd=self._project_dir,
            check=True,
        )
        if not _interpreter_for(self._venv_path).exists():
            raise EnvironmentError(
                f"uv venv finished but interpreter not found under "
                f"{self._venv_path}"
            )

    def validate(self) -> None:
        if not self._venv_path.exists():
            return
        interpreter = _interpreter_for(self._venv_path)
        if not interpreter.exists():
            raise EnvironmentError(
                f"venv at {self._venv_path} exists but has no interpreter "
                f"({interpreter} not found)"
            )

    def python_executable(self) -> Path:
        return _interpreter_for(self._venv_path)

    def executable(self, name: str) -> Path:
        return _executable_for(self._venv_path, name)

    def install_packages(
        self,
        requirements: Sequence[str],
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        return self._install_with_uv(
            self.python_executable(),
            requirements,
            force_reinstall=force_reinstall,
            no_deps=no_deps,
        )

    def describe(self) -> str:
        return f"venv at {self._venv_path}"


class CondaEnvironment(_UvBackend):
    """
    title: A conda/mamba environment reused by arxpm.
    attributes:
      _project_dir:
        type: Path
      _runner:
        type: CommandRunner
      _which:
        type: WhichFn
      _env_name:
        type: str | None
      _env_path:
        type: Path | None
      _cached_interpreter:
        type: Path | None
    """

    _env_name: str | None
    _env_path: Path | None
    _cached_interpreter: Path | None

    def __init__(
        self,
        project_dir: Path,
        name: str | None = None,
        path: str | None = None,
        runner: CommandRunner = run_command,
        which: WhichFn = shutil.which,
    ) -> None:
        super().__init__(project_dir, runner=runner, which=which)
        if name is None and path is None:
            raise EnvironmentError(
                "conda environment requires either name or path"
            )
        self._env_name = name
        self._env_path = (
            _resolve_venv_path(project_dir, path) if path is not None else None
        )
        self._cached_interpreter = None

    def ensure_ready(self) -> None:
        self._ensure_uv()
        self._validate_interpreter()

    def validate(self) -> None:
        self._validate_interpreter()

    def _validate_interpreter(self) -> None:
        interpreter = self.python_executable()
        if not interpreter.exists():
            raise EnvironmentError(
                f"conda environment interpreter not found: {interpreter}"
            )

    def python_executable(self) -> Path:
        if self._cached_interpreter is not None:
            return self._cached_interpreter
        if self._env_path is not None:
            interpreter = _interpreter_for(self._env_path)
        else:
            interpreter = self._resolve_by_name()
        self._cached_interpreter = interpreter
        return interpreter

    def _resolve_by_name(self) -> Path:
        name = self._env_name
        if name is None:
            raise EnvironmentError("conda environment has no name or path")
        if self._which("conda") is None:
            raise EnvironmentError(
                "conda is required to resolve environment by name but was "
                "not found on PATH"
            )
        result = self._runner(
            [
                "conda",
                "run",
                "-n",
                name,
                "python",
                "-c",
                "import sys; print(sys.executable)",
            ],
            cwd=self._project_dir,
            check=True,
        )
        lines = result.stdout.strip().splitlines()
        resolved = lines[-1] if lines else ""
        if not resolved:
            raise EnvironmentError(
                f"could not resolve python interpreter for conda env {name!r}"
            )
        return Path(resolved)

    def executable(self, name: str) -> Path:
        return self.python_executable().parent / _executable_name(name)

    def install_packages(
        self,
        requirements: Sequence[str],
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        return self._install_with_uv(
            self.python_executable(),
            requirements,
            force_reinstall=force_reinstall,
            no_deps=no_deps,
        )

    def describe(self) -> str:
        if self._env_path is not None:
            return f"conda env at {self._env_path}"
        return f"conda env {self._env_name!r}"


class SystemEnvironment(_UvBackend):
    """
    title: Install packages into the current Python environment.
    attributes:
      _project_dir:
        type: Path
      _runner:
        type: CommandRunner
      _which:
        type: WhichFn
    """

    def ensure_ready(self) -> None:
        self._ensure_uv()
        self.validate()

    def validate(self) -> None:
        interpreter = self.python_executable()
        if not interpreter.exists():
            raise EnvironmentError(
                f"system python interpreter not found: {interpreter}"
            )

    def python_executable(self) -> Path:
        return Path(sys.executable).resolve()

    def executable(self, name: str) -> Path:
        return Path(sysconfig.get_path("scripts")).resolve() / (
            _executable_name(name)
        )

    def install_packages(
        self,
        requirements: Sequence[str],
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        return self._install_with_uv(
            self.python_executable(),
            requirements,
            force_reinstall=force_reinstall,
            no_deps=no_deps,
        )

    def describe(self) -> str:
        return f"system python at {self.python_executable()}"


def build_environment(
    manifest: Manifest,
    project_dir: Path,
    runner: CommandRunner = run_command,
    which: WhichFn = shutil.which,
) -> EnvironmentRuntime:
    """
    title: Build the runtime from a manifest's environment configuration.
    parameters:
      manifest:
        type: Manifest
      project_dir:
        type: Path
      runner:
        type: CommandRunner
      which:
        type: WhichFn
    returns:
      type: EnvironmentRuntime
    """
    config = manifest.environment
    if config.kind == "venv":
        return UvManagedEnvironment(
            project_dir,
            venv_path=config.resolved_path() or DEFAULT_VENV_PATH,
            runner=runner,
            which=which,
        )
    if config.kind == "conda":
        return CondaEnvironment(
            project_dir,
            name=config.name,
            path=config.path,
            runner=runner,
            which=which,
        )
    if config.kind == "system":
        return SystemEnvironment(
            project_dir,
            runner=runner,
            which=which,
        )
    raise ManifestError(f"unsupported environment.kind: {config.kind!r}")


EnvironmentFactory = Callable[[Manifest, Path], EnvironmentRuntime]


def _resolve_venv_path(project_dir: Path, venv_path: str) -> Path:
    candidate = Path(venv_path)
    if candidate.is_absolute():
        return candidate
    return (project_dir / candidate).resolve()


def _interpreter_for(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _executable_for(environment_path: Path, name: str) -> Path:
    if sys.platform == "win32":
        return environment_path / "Scripts" / _executable_name(name)
    return environment_path / "bin" / _executable_name(name)


def _executable_name(name: str) -> str:
    suffix = ".exe" if sys.platform == "win32" else ""
    return f"{name}{suffix}"


def default_environment_config_from_cli(
    kind: str | None,
    path: str | None,
    name: str | None,
) -> EnvironmentConfig:
    """
    title: Translate CLI init flags into an EnvironmentConfig.
    parameters:
      kind:
        type: str | None
      path:
        type: str | None
      name:
        type: str | None
    returns:
      type: EnvironmentConfig
    """
    if kind is None and path is None and name is None:
        return EnvironmentConfig.default()
    resolved_kind = kind or "venv"
    return EnvironmentConfig(kind=resolved_kind, path=path, name=name)
