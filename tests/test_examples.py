"""
title: Unit tests covering the packaged Arx example projects.
"""

from __future__ import annotations

from pathlib import Path

from conftest import CopyExample, FakeEnvironment, FakeRunner

from arxpm.environment import EnvironmentFactory, EnvironmentRuntime
from arxpm.layout import resolve_build_config
from arxpm.manifest import load_manifest
from arxpm.models import Manifest
from arxpm.project import (
    ProjectService,
    _discover_arx_sources,
    _prepare_publish_workspace,
)


def _factory(env: FakeEnvironment) -> EnvironmentFactory:
    def _build(manifest: Manifest, project_dir: Path) -> EnvironmentRuntime:
        _ = manifest, project_dir
        return env

    return _build


def test_hello_arx_manifest_parses(copy_example: CopyExample) -> None:
    project_dir = copy_example("hello-arx")

    manifest = load_manifest(project_dir)
    layout = resolve_build_config(manifest, project_dir)

    assert manifest.project.name == "hello-arx"
    assert manifest.build.src_dir == "src"
    assert manifest.build.package == "hello_arx"
    assert manifest.build.mode == "app"
    assert layout.target_file == project_dir / "src" / "hello_arx" / "main.x"
    assert manifest.toolchain.compiler == "arx"


def test_hello_arx_build_invokes_arx_with_main_module(
    copy_example: CopyExample,
    fake_env: FakeEnvironment,
    fake_runner: FakeRunner,
) -> None:
    project_dir = copy_example("hello-arx")
    service = ProjectService(
        environment_factory=_factory(fake_env),
        runner=fake_runner,
    )

    service.build(project_dir)

    assert fake_runner.calls[0][0] == [
        "/fake/python",
        "-m",
        "arx",
        "src/hello_arx/main.x",
        "--output-file",
        "build/hello_arx",
    ]


def test_hello_arx_discover_arx_sources(copy_example: CopyExample) -> None:
    project_dir = copy_example("hello-arx")
    layout = resolve_build_config(load_manifest(project_dir), project_dir)

    sources = _discover_arx_sources(project_dir, layout.source_root)

    assert sources == [
        Path("src/hello_arx/__init__.x"),
        Path("src/hello_arx/main.x"),
    ]


def test_multi_module_manifest_parses(copy_example: CopyExample) -> None:
    project_dir = copy_example("multi-module")

    manifest = load_manifest(project_dir)
    layout = resolve_build_config(manifest, project_dir)

    assert manifest.project.name == "multi-module"
    assert manifest.build.src_dir == "src"
    assert manifest.build.package == "multi_module"
    assert manifest.build.mode == "app"
    assert layout.target_file == (
        project_dir / "src" / "multi_module" / "main.x"
    )


def test_multi_module_build_invokes_arx_with_main_module(
    copy_example: CopyExample,
    fake_env: FakeEnvironment,
    fake_runner: FakeRunner,
) -> None:
    project_dir = copy_example("multi-module")
    service = ProjectService(
        environment_factory=_factory(fake_env),
        runner=fake_runner,
    )

    service.build(project_dir)

    assert fake_runner.calls[0][0] == [
        "/fake/python",
        "-m",
        "arx",
        "src/multi_module/main.x",
        "--output-file",
        "build/multi_module",
    ]


def test_multi_module_discover_arx_sources_finds_all_modules(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("multi-module")
    layout = resolve_build_config(load_manifest(project_dir), project_dir)

    sources = _discover_arx_sources(project_dir, layout.source_root)

    assert sources == [
        Path("src/multi_module/__init__.x"),
        Path("src/multi_module/main.x"),
        Path("src/multi_module/math_utils.x"),
        Path("src/multi_module/string_utils.x"),
    ]


def test_multi_module_main_declares_expected_imports(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("multi-module")
    main_text = (project_dir / "src" / "multi_module" / "main.x").read_text(
        encoding="utf-8"
    )

    assert "import add from math_utils" in main_text
    assert "import greet from string_utils" in main_text
    assert "add(2, 3)" in main_text
    assert 'greet("Arx")' in main_text


def test_local_lib_manifest_declares_lib_mode(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local_lib")

    manifest = load_manifest(project_dir)
    layout = resolve_build_config(manifest, project_dir)

    assert manifest.project.name == "local_lib"
    assert manifest.build.src_dir == "src"
    assert manifest.build.package is None
    assert manifest.build.mode == "lib"
    assert layout.target_file == (
        project_dir / "src" / "local_lib" / "__init__.x"
    )


def test_local_lib_exposes_stats_module_at_top_level(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local_lib")
    layout = resolve_build_config(load_manifest(project_dir), project_dir)

    sources = _discover_arx_sources(project_dir, layout.source_root)

    assert sources == [
        Path("src/local_lib/__init__.x"),
        Path("src/local_lib/stats.x"),
    ]


def test_local_consumer_manifest_declares_local_lib_path_dep(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local-consumer")

    manifest = load_manifest(project_dir)
    layout = resolve_build_config(manifest, project_dir)

    assert manifest.project.name == "local-consumer"
    assert manifest.build.src_dir == "src"
    assert manifest.build.package == "local_consumer"
    assert manifest.build.mode == "app"
    assert layout.target_file == (
        project_dir / "src" / "local_consumer" / "main.x"
    )
    assert manifest.dependencies["local_lib"].path == "../local_lib"
    assert manifest.dependencies["pyyaml"].kind == "registry"


def test_local_consumer_imports_from_local_lib(
    copy_example: CopyExample,
) -> None:
    project_dir = copy_example("local-consumer")
    main_text = (project_dir / "src" / "local_consumer" / "main.x").read_text(
        encoding="utf-8"
    )

    assert "import sum2 from local_lib.stats" in main_text
    assert "sum2(2, 3)" in main_text


def test_local_consumer_build_invokes_arx_with_main_module(
    copy_example: CopyExample,
    fake_env: FakeEnvironment,
    fake_runner: FakeRunner,
) -> None:
    project_dir = copy_example("local-consumer")
    service = ProjectService(
        environment_factory=_factory(fake_env),
        runner=fake_runner,
    )

    service.build(project_dir)

    assert fake_runner.calls[0][0] == [
        "/fake/python",
        "-m",
        "arx",
        "src/local_consumer/main.x",
        "--output-file",
        "build/local_consumer",
    ]


def test_local_lib_publish_workspace_bundles_all_arx_sources(
    copy_example: CopyExample,
    tmp_path: Path,
) -> None:
    project_dir = copy_example("local_lib")
    manifest = load_manifest(project_dir)
    staging_dir = tmp_path / "staging"

    _prepare_publish_workspace(project_dir, manifest, staging_dir)

    package_root = staging_dir / "src" / "local_lib"
    assert (package_root / "__init__.x").is_file()
    assert (package_root / "stats.x").is_file()
    assert (package_root / ".arxproject.toml").is_file()
    assert (package_root / "__init__.py").is_file()

    pyproject_text = (staging_dir / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'packages = ["src/local_lib"]' in pyproject_text
    assert '"src/local_lib/**/*.x"' in pyproject_text
    assert 'name = "local_lib"' in pyproject_text
