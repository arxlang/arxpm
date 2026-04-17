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


def test_init_is_idempotent_when_manifest_exists(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    first = service.init(tmp_path, name="demo", create_pixi=False)
    entry_path = tmp_path / first.build.entry
    entry_path.write_text("// existing source\n", encoding="utf-8")

    second = service.init(tmp_path, name="ignored", create_pixi=True)

    assert second.project.name == "demo"
    assert entry_path.read_text(encoding="utf-8") == "// existing source\n"
    assert pixi.ensure_manifest_calls


def test_install_packs_and_symlinks_arx_path_dependency(
    tmp_path: Path,
) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    library_dir = tmp_path / "mylib"
    consumer_dir = tmp_path / "app"
    service.init(library_dir, name="mylib", create_pixi=False)
    service.init(consumer_dir, name="app", create_pixi=False)
    service.add_dependency(consumer_dir, "mylib", path=Path("../mylib"))

    fake_install_dir = tmp_path / "fake-site-packages" / "mylib"
    fake_install_dir.mkdir(parents=True)
    (fake_install_dir / "main.x").write_text("", encoding="utf-8")
    pixi.module_install_dirs["mylib"] = fake_install_dir

    service.install(consumer_dir)

    consumer_run_calls = [
        args for cwd, args in pixi.run_calls if cwd == consumer_dir
    ]
    pip_install_commands = [
        args
        for args in consumer_run_calls
        if args[:4] == ["python", "-m", "pip", "install"]
        and any(str(arg).endswith(".whl") for arg in args)
    ]
    assert pip_install_commands, (
        "expected the consumer to pip-install the library's wheel"
    )
    probe_commands = [
        args
        for args in consumer_run_calls
        if args[:2] == ["python", "-c"]
        and "import mylib" in (args[2] if len(args) > 2 else "")
    ]
    assert probe_commands, "expected a python -c probe for the install dir"

    symlink = consumer_dir / "mylib"
    assert symlink.is_symlink()
    assert symlink.resolve() == fake_install_dir


def test_install_rejects_arx_path_dep_name_mismatch(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    library_dir = tmp_path / "weird_dir_name"
    consumer_dir = tmp_path / "app"
    service.init(library_dir, name="actual_module", create_pixi=False)
    service.init(consumer_dir, name="app", create_pixi=False)
    service.add_dependency(
        consumer_dir, "declared_name", path=Path("../weird_dir_name")
    )

    with pytest.raises(ManifestError, match="must match the library"):
        service.install(consumer_dir)
