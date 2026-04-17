"""
title: Shared fixtures for arxpm tests.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from arxpm.external import CommandResult
from arxpm.manifest import load_manifest

ManifestCall = tuple[Path, str, tuple[str, ...]]
CopyExample = Callable[[str], Path]

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples"


class FakePixiService:
    """
    title: Pixi test double.
    attributes:
      ensure_manifest_calls:
        type: list[ManifestCall]
      install_calls:
        type: list[Path]
      run_calls:
        type: list[tuple[Path, list[str]]]
      module_install_dirs:
        type: dict[str, Path]
    """

    def __init__(self) -> None:
        self.ensure_manifest_calls: list[ManifestCall] = []
        self.install_calls: list[Path] = []
        self.run_calls: list[tuple[Path, list[str]]] = []
        self.module_install_dirs: dict[str, Path] = {}

    def ensure_available(self) -> None:
        return None

    def ensure_manifest(
        self,
        directory: Path,
        project_name: str,
        required_dependencies: tuple[str, ...],
    ) -> Path:
        self.ensure_manifest_calls.append(
            (directory, project_name, required_dependencies)
        )
        return directory / "pixi.toml"

    def install(self, directory: Path) -> CommandResult:
        self.install_calls.append(directory)
        return CommandResult(("pixi", "install"), 0, "", "")

    def run(self, directory: Path, args: list[str]) -> CommandResult:
        self.run_calls.append((directory, args))

        if args[:3] == ["python", "-m", "build"] and "--outdir" in args:
            outdir_value = Path(args[args.index("--outdir") + 1])
            if outdir_value.is_absolute():
                outdir = outdir_value
            else:
                outdir = directory / outdir_value
            outdir.mkdir(parents=True, exist_ok=True)

            manifest = load_manifest(directory)
            normalized = manifest.project.name.replace("-", "_")
            version = manifest.project.version
            (outdir / f"{normalized}-{version}.tar.gz").write_text(
                "",
                encoding="utf-8",
            )
            (outdir / f"{normalized}-{version}-py3-none-any.whl").write_text(
                "",
                encoding="utf-8",
            )

        if args[:2] == ["python", "-c"]:
            script = args[2] if len(args) > 2 else ""
            for module_name, install_dir in self.module_install_dirs.items():
                if f"import {module_name}" in script:
                    return CommandResult(
                        ("pixi", "run", *args),
                        0,
                        f"{install_dir}\n",
                        "",
                    )

        return CommandResult(("pixi", "run", *args), 0, "", "")


@pytest.fixture
def fake_pixi() -> FakePixiService:
    """
    title: Provide a fresh FakePixiService per test.
    returns:
      type: FakePixiService
    """
    return FakePixiService()


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
