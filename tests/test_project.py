"""
title: Tests for project workflow operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arxpm.errors import ManifestError
from arxpm.external import CommandResult
from arxpm.manifest import load_manifest
from arxpm.project import ProjectService

ManifestCall = tuple[Path, str, tuple[str, ...]]


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
    """

    def __init__(self) -> None:
        self.ensure_manifest_calls: list[ManifestCall] = []
        self.install_calls: list[Path] = []
        self.run_calls: list[tuple[Path, list[str]]] = []

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
        return CommandResult(("pixi", "run", *args), 0, "", "")


def test_init_and_add_dependency_forms(tmp_path: Path) -> None:
    service = ProjectService(pixi=FakePixiService())

    service.init(tmp_path, name="demo", create_pixi=False)
    service.add_dependency(tmp_path, "http")
    service.add_dependency(tmp_path, "mylib", path=Path("../mylib"))
    service.add_dependency(
        tmp_path,
        "utils",
        git="https://example.com/utils.git",
    )

    manifest = load_manifest(tmp_path)
    assert manifest.dependencies["http"].kind == "registry"
    assert manifest.dependencies["mylib"].path == "../mylib"
    assert (
        manifest.dependencies["utils"].git == "https://example.com/utils.git"
    )


def test_build_and_run_delegate_to_pixi(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    build_result = service.build(tmp_path)
    run_result = service.run(tmp_path)

    assert build_result.artifact == tmp_path / "build" / "demo"
    assert pixi.run_calls[0][1][:3] == [
        "arx",
        "src/main.x",
        "--output-file",
    ]
    assert pixi.run_calls[-1][1] == ["build/demo"]
    assert run_result.build_result.artifact == tmp_path / "build" / "demo"


def test_install_calls_pixi_install(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    service.install(tmp_path)

    assert pixi.install_calls == [tmp_path]
    assert pixi.ensure_manifest_calls


def test_install_requires_arxproj_manifest(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    with pytest.raises(ManifestError):
        service.install(tmp_path)
