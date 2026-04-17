"""
title: Unit tests covering the packaged Arx example projects.
"""

from __future__ import annotations

from pathlib import Path

from conftest import CopyExample, FakePixiService

from arxpm.manifest import load_manifest
from arxpm.project import (
    ProjectService,
    _arx_module_name,
    _discover_arx_sources,
    _prepare_publish_workspace,
)


def test_hello_arx_manifest_parses(copy_example: CopyExample) -> None:
    project_dir = copy_example("hello-arx")

    manifest = load_manifest(project_dir)

    assert manifest.project.name == "hello-arx"
    assert manifest.build.src_dir == "src"
    assert manifest.build.entry == "main.x"
    assert manifest.build.source_path == "src/main.x"
    assert manifest.toolchain.compiler == "arx"


def test_hello_arx_build_invokes_arx_with_entry_only(
    copy_example: CopyExample,
    fake_pixi: FakePixiService,
) -> None:
    project_dir = copy_example("hello-arx")
    service = ProjectService(pixi=fake_pixi)

    service.build(project_dir)

    assert fake_pixi.run_calls[0][1] == [
        "arx",
        "src/main.x",
        "--output-file",
        "build/hello-arx",
    ]


def test_hello_arx_discover_arx_sources(copy_example: CopyExample) -> None:
    project_dir = copy_example("hello-arx")

    sources = _discover_arx_sources(project_dir)

    assert sources == [Path("src/main.x")]


def test_multi_module_manifest_parses(copy_example: CopyExample) -> None:
    project_dir = copy_example("multi-module")

    manifest = load_manifest(project_dir)

    assert manifest.project.name == "multi-module"
    assert manifest.build.src_dir == "src"
    assert manifest.build.entry == "main.x"
    assert manifest.build.source_path == "src/main.x"


def test_multi_module_build_invokes_arx_with_entry_only(
    copy_example: CopyExample,
    fake_pixi: FakePixiService,
) -> None:
    project_dir = copy_example("multi-module")
    service = ProjectService(pixi=fake_pixi)

    service.build(project_dir)

    assert fake_pixi.run_calls[0][1] == [
        "arx",
        "src/main.x",
        "--output-file",
        "build/multi-module",
    ]


def test_multi_module_discover_arx_sources_finds_all_modules(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("multi-module")

    sources = _discover_arx_sources(project_dir)

    assert sources == [
        Path("src/main.x"),
        Path("src/math_utils.x"),
        Path("src/string_utils.x"),
    ]


def test_multi_module_main_declares_expected_imports(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("multi-module")
    main_text = (project_dir / "src" / "main.x").read_text(encoding="utf-8")

    assert "import add from math_utils" in main_text
    assert "import greet from string_utils" in main_text
    assert "add(2, 3)" in main_text
    assert 'greet("Arx")' in main_text


def test_local_lib_manifest_declares_underscore_package(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local_lib")

    manifest = load_manifest(project_dir)

    assert manifest.project.name == "local_lib"
    assert manifest.build.src_dir == "src"
    assert manifest.build.entry == "local_lib.x"
    assert manifest.build.source_path == "src/local_lib.x"


def test_local_lib_exposes_stats_module_at_top_level(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local_lib")

    sources = _discover_arx_sources(project_dir)

    assert sources == [
        Path("src/local_lib.x"),
        Path("src/stats.x"),
    ]


def test_local_consumer_manifest_declares_local_lib_path_dep(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local-consumer")

    manifest = load_manifest(project_dir)

    assert manifest.project.name == "local-consumer"
    assert manifest.build.src_dir == "src"
    assert manifest.build.entry == "main.x"
    assert manifest.build.source_path == "src/main.x"
    assert manifest.dependencies["local_lib"].path == "../local_lib"
    assert manifest.dependencies["pyyaml"].kind == "registry"


def test_local_consumer_imports_from_local_lib(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local-consumer")
    main_text = (project_dir / "src" / "main.x").read_text(encoding="utf-8")

    assert "import sum2 from local_lib.stats" in main_text
    assert "sum2(2, 3)" in main_text


def test_local_consumer_build_invokes_arx_with_entry_only(
    copy_example: CopyExample,
    fake_pixi: FakePixiService,
) -> None:
    project_dir = copy_example("local-consumer")
    service = ProjectService(pixi=fake_pixi)

    service.build(project_dir)

    assert fake_pixi.run_calls[0][1] == [
        "arx",
        "src/main.x",
        "--output-file",
        "build/local-consumer",
    ]


def test_local_lib_publish_workspace_bundles_all_arx_sources(
    copy_example: CopyExample,
    tmp_path: Path,
) -> None:
    project_dir = copy_example("local_lib")
    manifest = load_manifest(project_dir)
    staging_dir = tmp_path / "staging"

    _prepare_publish_workspace(project_dir, manifest, staging_dir)

    package_name = _arx_module_name(manifest.project.name)
    package_root = staging_dir / "src" / package_name
    assert package_name == "local_lib"
    assert (package_root / "local_lib.x").is_file()
    assert (package_root / "stats.x").is_file()
    assert (package_root / ".arxproject.toml").is_file()
    assert (package_root / "__init__.py").is_file()

    pyproject_text = (staging_dir / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'packages = ["src/local_lib"]' in pyproject_text
    assert '"src/local_lib/**/*.x"' in pyproject_text
    assert 'name = "local_lib"' in pyproject_text
