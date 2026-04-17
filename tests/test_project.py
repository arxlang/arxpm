"""
title: Tests for project workflow operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakePixiService

from arxpm.errors import ManifestError
from arxpm.manifest import load_manifest
from arxpm.project import ProjectService


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


def test_install_installs_manifest_dependencies_with_pip(
    tmp_path: Path,
) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    service.add_dependency(tmp_path, "http")
    service.add_dependency(tmp_path, "mylib", path=Path("../mylib"))
    service.add_dependency(
        tmp_path,
        "utils",
        git="https://example.com/utils.git",
    )

    service.install(tmp_path)

    commands = [call[1] for call in pixi.run_calls]
    assert commands == [
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "http",
        ],
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "../mylib",
        ],
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "git+https://example.com/utils.git",
        ],
    ]


def test_publish_builds_and_uploads_artifacts(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    publish_result = service.publish(
        tmp_path,
        repository_url="https://test.pypi.org/legacy/",
        skip_existing=True,
    )

    assert [path.name for path in publish_result.artifacts] == [
        "demo-0.1.0-py3-none-any.whl",
        "demo-0.1.0.tar.gz",
    ]
    assert publish_result.upload_result is not None
    assert pixi.install_calls == [tmp_path]

    commands = [call[1] for call in pixi.run_calls]
    assert commands[0][:5] == [
        "python",
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
    ]
    assert commands[1][:3] == ["python", "-m", "build"]

    upload_command = commands[2]
    assert upload_command[:4] == ["python", "-m", "twine", "upload"]
    assert "--repository-url" in upload_command
    assert "--skip-existing" in upload_command


def test_pack_builds_artifacts_without_upload(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    pack_result = service.pack(tmp_path)

    assert [path.name for path in pack_result.artifacts] == [
        "demo-0.1.0-py3-none-any.whl",
        "demo-0.1.0.tar.gz",
    ]
    assert pack_result.upload_result is None
    assert len(pixi.run_calls) == 2


def test_publish_dry_run_skips_upload(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    publish_result = service.publish(tmp_path, dry_run=True)

    assert publish_result.upload_result is None
    assert len(pixi.run_calls) == 2


def test_install_requires_arxproject_manifest(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    with pytest.raises(ManifestError):
        service.install(tmp_path)
