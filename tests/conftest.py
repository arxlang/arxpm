"""
title: Shared fixtures for arxpm tests.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from arxpm.external import CommandResult
from arxpm.manifest import load_manifest

CopyExample = Callable[[str], Path]
InstallCall = tuple[tuple[str, ...], bool, bool]

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples"


class FakeEnvironment:
    """
    title: Environment runtime test double.
    attributes:
      ensure_ready_calls:
        type: int
      install_calls:
        type: list[InstallCall]
      python_path:
        type: Path
      module_install_dirs:
        type: dict[str, Path]
    """

    ensure_ready_calls: int
    install_calls: list[InstallCall]
    python_path: Path
    module_install_dirs: dict[str, Path]

    def __init__(self, python_path: Path | None = None) -> None:
        self.ensure_ready_calls = 0
        self.install_calls = []
        self.python_path = python_path or Path("/fake/python")
        self.module_install_dirs = {}

    def ensure_ready(self) -> None:
        self.ensure_ready_calls += 1

    def python_executable(self) -> Path:
        return self.python_path

    def install_packages(
        self,
        requirements: Sequence[str],
        *,
        force_reinstall: bool = False,
        no_deps: bool = False,
    ) -> CommandResult:
        self.install_calls.append(
            (tuple(requirements), force_reinstall, no_deps)
        )
        return CommandResult(("uv", "pip", "install"), 0, "", "")

    def describe(self) -> str:
        return "fake environment"


class FakeRunner:
    """
    title: Command runner test double.
    attributes:
      calls:
        type: list[tuple[list[str], Path | None, bool]]
      module_install_dirs:
        type: dict[str, Path]
    """

    calls: list[tuple[list[str], Path | None, bool]]
    module_install_dirs: dict[str, Path]

    def __init__(
        self,
        module_install_dirs: dict[str, Path] | None = None,
    ) -> None:
        self.calls = []
        self.module_install_dirs = module_install_dirs or {}

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        cmd_list = list(command)
        self.calls.append((cmd_list, cwd, check))

        if "-m" in cmd_list and "build" in cmd_list and "--outdir" in cmd_list:
            outdir_value = Path(cmd_list[cmd_list.index("--outdir") + 1])
            if outdir_value.is_absolute():
                outdir = outdir_value
            else:
                outdir = (cwd or Path(".")) / outdir_value
            outdir.mkdir(parents=True, exist_ok=True)

            if cwd is not None:
                manifest = load_manifest(cwd)
                normalized = manifest.project.name.replace("-", "_")
                version = manifest.project.version
                (outdir / f"{normalized}-{version}.tar.gz").write_text(
                    "",
                    encoding="utf-8",
                )
                (
                    outdir / f"{normalized}-{version}-py3-none-any.whl"
                ).write_text(
                    "",
                    encoding="utf-8",
                )

        if len(cmd_list) >= 3 and cmd_list[1] == "-c":
            script = cmd_list[2]
            for module_name, install_dir in self.module_install_dirs.items():
                if f"import {module_name}" in script:
                    return CommandResult(
                        tuple(cmd_list),
                        0,
                        f"{install_dir}\n",
                        "",
                    )

        return CommandResult(tuple(cmd_list), 0, "", "")


@pytest.fixture
def fake_env() -> FakeEnvironment:
    """
    title: Provide a fresh FakeEnvironment per test.
    returns:
      type: FakeEnvironment
    """
    return FakeEnvironment()


@pytest.fixture
def fake_runner() -> FakeRunner:
    """
    title: Provide a fresh FakeRunner per test.
    returns:
      type: FakeRunner
    """
    return FakeRunner()


@pytest.fixture
def copy_example(tmp_path: Path) -> CopyExample:
    """
    title: Copy a packaged example into tmp_path and return its path.
    parameters:
      tmp_path:
        type: Path
    returns:
      type: CopyExample
    """

    def _copy(name: str) -> Path:
        source = _EXAMPLES_ROOT / name
        if not source.is_dir():
            raise FileNotFoundError(f"example not found: {source}")
        destination = tmp_path / name
        shutil.copytree(source, destination)
        return destination

    return _copy
