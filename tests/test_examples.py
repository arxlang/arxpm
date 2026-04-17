"""
title: Unit tests covering the packaged Arx example projects.
"""

from __future__ import annotations

from pathlib import Path

from conftest import CopyExample, FakePixiService

from arxpm.manifest import load_manifest
from arxpm.project import ProjectService, _discover_arx_sources


def test_hello_arx_manifest_parses(copy_example: CopyExample) -> None:
    project_dir = copy_example("hello-arx")

    manifest = load_manifest(project_dir)

    assert manifest.project.name == "hello-arx"
    assert manifest.build.entry == "src/main.x"
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
    assert manifest.build.entry == "src/main.x"


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
