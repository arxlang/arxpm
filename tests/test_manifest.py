"""
title: Tests for .arxproject.toml parsing and rendering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arxpm.errors import ManifestError
from arxpm.manifest import (
    create_default_manifest,
    load_manifest_file,
    render_manifest,
    save_manifest_file,
)
from arxpm.models import (
    BuildSystemConfig,
    DependencyGroupInclude,
    DependencySpec,
    EnvironmentConfig,
    Manifest,
    ProjectConfig,
    effective_build_system_dependencies,
)


def test_manifest_round_trip(tmp_path: Path) -> None:
    manifest = create_default_manifest("hello-arx")
    path = tmp_path / ".arxproject.toml"

    save_manifest_file(manifest, path)
    loaded = load_manifest_file(path)

    assert loaded.project.name == "hello-arx"
    assert loaded.project.version == "0.1.0"
    assert loaded.build.src_dir == "src"
    assert loaded.build.out_dir == "build"
    assert loaded.build.package is None
    assert loaded.build.mode is None
    assert loaded.project.requires_arx is not None
    assert loaded.build_system is not None
    assert loaded.build_system.dependencies[0].startswith("arxlang>=")
    assert loaded.environment.kind == "venv"


def test_manifest_parses_all_dependency_forms(tmp_path: Path) -> None:
    content = """
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"
dependencies = [
  "http",
  "requests>=2.31",
  "mylib @ ../mylib",
  "utils @ git+https://example.com/utils.git",
]

[build]
package = "hello_arx"
mode = "app"
out_dir = "build"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    manifest = load_manifest_file(path)

    assert manifest.build.package == "hello_arx"
    assert manifest.build.mode == "app"
    assert manifest.dependencies["http"].kind == "registry"
    assert manifest.dependencies["requests"].version_constraint == ">=2.31"
    assert manifest.dependencies["mylib"].path == "../mylib"
    assert (
        manifest.dependencies["utils"].git == "https://example.com/utils.git"
    )


def test_manifest_parses_requires_arx_and_build_system(
    tmp_path: Path,
) -> None:
    content = """
[project]
name = "hello-arx"
version = "0.1.0"
requires-arx = ">=1.0,<2"

[build-system]
dependencies = [
  "some-build-helper>=0.3",
]
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    manifest = load_manifest_file(path)

    assert manifest.project.requires_arx == ">=1.0,<2"
    assert manifest.build_system == BuildSystemConfig(
        dependencies=("some-build-helper>=0.3",)
    )
    assert effective_build_system_dependencies(manifest) == [
        "arxlang>=1.0,<2",
        "some-build-helper>=0.3",
    ]


def test_manifest_rejects_removed_build_entry(tmp_path: Path) -> None:
    content = """
[project]
name = "legacy"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(
        ManifestError,
        match=r"\[build\]\.entry is no longer supported",
    ):
        load_manifest_file(path)


def test_manifest_rejects_unknown_top_level_table(tmp_path: Path) -> None:
    content = """
[project]
name = "legacy"
version = "0.1.0"
edition = "2026"

[arxpm]
resolver = "future"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(
        ManifestError, match=r"manifest has unknown top-level keys: arxpm"
    ):
        load_manifest_file(path)


def test_manifest_rejects_legacy_dependencies_table(tmp_path: Path) -> None:
    content = """
[project]
name = "legacy"
version = "0.1.0"
edition = "2026"

[dependencies]
http = { source = "registry" }
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(
        ManifestError, match=r"top-level \[dependencies\] table"
    ):
        load_manifest_file(path)


def test_manifest_rejects_removed_toolchain_section(tmp_path: Path) -> None:
    content = """
[project]
name = "legacy"
version = "0.1.0"
edition = "2026"

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(
        ManifestError,
        match=r"does not support \[toolchain\] sections",
    ):
        load_manifest_file(path)


def test_manifest_rejects_invalid_dependency_value(tmp_path: Path) -> None:
    content = """
[project]
name = "bad"
version = "0.1.0"
edition = "2026"
dependencies = ["bad @"]
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(ManifestError):
        load_manifest_file(path)


def test_manifest_round_trip_preserves_dependencies(tmp_path: Path) -> None:
    manifest = Manifest(
        project=ProjectConfig(name="demo"),
        dependencies={
            "pyyaml": DependencySpec.registry(">=6"),
            "local_lib": DependencySpec.from_path("../local_lib"),
            "utils": DependencySpec.from_git("https://example.com/utils.git"),
        },
    )
    path = tmp_path / ".arxproject.toml"
    path.write_text(render_manifest(manifest), encoding="utf-8")

    loaded = load_manifest_file(path)

    assert loaded.dependencies["pyyaml"].kind == "registry"
    assert loaded.dependencies["pyyaml"].version_constraint == ">=6"
    assert loaded.dependencies["local_lib"].path == "../local_lib"
    assert loaded.dependencies["utils"].git == "https://example.com/utils.git"


def test_manifest_round_trip_preserves_dependency_groups(
    tmp_path: Path,
) -> None:
    manifest = Manifest(
        project=ProjectConfig(name="demo"),
        dependency_groups={
            "lint": ("ruff",),
            "dev-test": (
                DependencyGroupInclude("lint"),
                "pytest",
            ),
        },
    )
    path = tmp_path / ".arxproject.toml"
    path.write_text(render_manifest(manifest), encoding="utf-8")

    loaded = load_manifest_file(path)

    assert loaded.dependency_groups["lint"] == ("ruff",)
    dev_test = loaded.dependency_groups["dev-test"]
    assert isinstance(dev_test[0], DependencyGroupInclude)
    assert dev_test[0].include_group == "lint"
    assert dev_test[1] == "pytest"


def _write_manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".arxproject.toml"
    path.write_text(body + "\n", encoding="utf-8")
    return path


_BASE_MANIFEST = """
[project]
name = "demo"
version = "0.1.0"
edition = "2026"
dependencies = []

[build]
out_dir = "build"
mode = "app"
""".strip()


def test_environment_defaults_when_section_absent(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _BASE_MANIFEST)
    manifest = load_manifest_file(path)

    assert manifest.environment.is_default()
    assert manifest.environment.kind == "venv"


def test_environment_venv_with_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "venv"
path = ".venv-custom"
"""
    path = _write_manifest(tmp_path, body)
    manifest = load_manifest_file(path)

    assert manifest.environment.kind == "venv"
    assert manifest.environment.path == ".venv-custom"


def test_environment_venv_rejects_name(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "venv"
name = "nope"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(
        ManifestError, match=r"environment.name is not allowed"
    ):
        load_manifest_file(path)


def test_environment_conda_requires_name_or_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "conda"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(
        ManifestError,
        match=r"environment requires 'name' or 'path'",
    ):
        load_manifest_file(path)


def test_environment_conda_with_name(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "conda"
name = "demo-env"
"""
    path = _write_manifest(tmp_path, body)
    manifest = load_manifest_file(path)

    assert manifest.environment.kind == "conda"
    assert manifest.environment.name == "demo-env"


def test_environment_system_disallows_path_and_name(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "system"
path = "/tmp/python"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(
        ManifestError,
        match=r"environment.path and environment.name are not allowed",
    ):
        load_manifest_file(path)


def test_manifest_round_trip_preserves_environment(tmp_path: Path) -> None:
    manifest = Manifest(
        project=ProjectConfig(name="demo"),
        environment=EnvironmentConfig(kind="system"),
    )
    path = tmp_path / ".arxproject.toml"
    path.write_text(render_manifest(manifest), encoding="utf-8")

    loaded = load_manifest_file(path)

    assert loaded.environment.kind == "system"
    assert loaded.environment.path is None
    assert loaded.environment.name is None


def test_manifest_loads_minimal_shape(tmp_path: Path) -> None:
    content = """
[project]
name = "tiny"
version = "0.0.1"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    manifest = load_manifest_file(path)

    assert manifest.project.name == "tiny"
    assert manifest.project.version == "0.0.1"
    assert manifest.project.edition == "2026"
    assert manifest.build.src_dir == "src"
    assert manifest.build.out_dir == "build"
    assert manifest.build.package is None
    assert manifest.build.mode is None
    assert manifest.build_system is None
    assert effective_build_system_dependencies(manifest) == ["arxlang"]
    assert manifest.environment.is_default()
