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
    save_manifest_file,
)


def test_manifest_round_trip(tmp_path: Path) -> None:
    manifest = create_default_manifest("hello-arx")
    path = tmp_path / ".arxproject.toml"

    save_manifest_file(manifest, path)
    loaded = load_manifest_file(path)

    assert loaded.project.name == "hello-arx"
    assert loaded.project.version == "0.1.0"
    assert loaded.build.src_dir == "src"
    assert loaded.build.entry == "main.x"
    assert loaded.build.source_path == "src/main.x"
    assert loaded.toolchain.linker == "clang"


def test_manifest_parses_all_dependency_forms(tmp_path: Path) -> None:
    content = """
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"
dependencies = [
  "http",
  "mylib @ ../mylib",
  "utils @ git+https://example.com/utils.git",
]

[build]
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    manifest = load_manifest_file(path)

    assert manifest.dependencies["http"].kind == "registry"
    assert manifest.dependencies["mylib"].path == "../mylib"
    assert (
        manifest.dependencies["utils"].git == "https://example.com/utils.git"
    )


def test_manifest_parses_dev_dependencies(tmp_path: Path) -> None:
    content = """
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"
dependencies = ["pyyaml"]

[build]
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"

[arxpm.dependencies-dev]
dependencies = ["makim"]
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    manifest = load_manifest_file(path)

    assert manifest.dependencies["pyyaml"].kind == "registry"
    assert manifest.dev_dependencies["makim"].kind == "registry"


def test_manifest_rejects_legacy_dependencies_table(tmp_path: Path) -> None:
    content = """
[project]
name = "legacy"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
out_dir = "build"

[dependencies]
http = { source = "registry" }

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(ManifestError, match="no longer supported"):
        load_manifest_file(path)


def test_manifest_rejects_invalid_dependency_value(tmp_path: Path) -> None:
    content = """
[project]
name = "bad"
version = "0.1.0"
edition = "2026"
dependencies = ["bad @"]

[build]
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(ManifestError):
        load_manifest_file(path)


def test_manifest_round_trip_preserves_dependencies(tmp_path: Path) -> None:
    from arxpm.manifest import render_manifest
    from arxpm.models import DependencySpec, Manifest, ProjectConfig

    manifest = Manifest(
        project=ProjectConfig(name="demo"),
        dependencies={
            "pyyaml": DependencySpec.registry(),
            "local_lib": DependencySpec.from_path("../local_lib"),
            "utils": DependencySpec.from_git("https://example.com/utils.git"),
        },
        dev_dependencies={"makim": DependencySpec.registry()},
    )
    path = tmp_path / ".arxproject.toml"
    path.write_text(render_manifest(manifest), encoding="utf-8")

    loaded = load_manifest_file(path)

    assert loaded.dependencies["pyyaml"].kind == "registry"
    assert loaded.dependencies["local_lib"].path == "../local_lib"
    assert loaded.dependencies["utils"].git == "https://example.com/utils.git"
    assert loaded.dev_dependencies["makim"].kind == "registry"


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
entry = "src/main.x"
out_dir = "build"

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()


def test_environment_defaults_when_section_absent(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _BASE_MANIFEST)
    manifest = load_manifest_file(path)

    assert manifest.environment.is_default()
    assert manifest.environment.kind == "managed-venv"


def test_environment_managed_venv_with_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "managed-venv"
path = ".venv-custom"
"""
    path = _write_manifest(tmp_path, body)
    manifest = load_manifest_file(path)

    assert manifest.environment.kind == "managed-venv"
    assert manifest.environment.path == ".venv-custom"


def test_environment_existing_venv_requires_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "existing-venv"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(ManifestError, match="existing-venv"):
        load_manifest_file(path)


def test_environment_existing_venv_parses_with_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "existing-venv"
path = "/opt/project/venv"
"""
    path = _write_manifest(tmp_path, body)
    manifest = load_manifest_file(path)

    assert manifest.environment.kind == "existing-venv"
    assert manifest.environment.path == "/opt/project/venv"


def test_environment_conda_requires_name_or_path(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "conda"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(ManifestError, match="conda"):
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


def test_environment_rejects_unknown_kind(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "bogus"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(ManifestError, match="environment.kind"):
        load_manifest_file(path)


def test_environment_managed_venv_rejects_name(tmp_path: Path) -> None:
    body = f"""{_BASE_MANIFEST}

[environment]
kind = "managed-venv"
name = "nope"
"""
    path = _write_manifest(tmp_path, body)

    with pytest.raises(ManifestError, match="managed-venv"):
        load_manifest_file(path)


def test_environment_round_trips_through_render(tmp_path: Path) -> None:
    from arxpm.manifest import render_manifest
    from arxpm.models import EnvironmentConfig, Manifest, ProjectConfig

    manifest = Manifest(
        project=ProjectConfig(name="demo"),
        environment=EnvironmentConfig(kind="conda", name="demo-env"),
    )
    path = tmp_path / ".arxproject.toml"
    path.write_text(render_manifest(manifest), encoding="utf-8")

    loaded = load_manifest_file(path)

    assert loaded.environment.kind == "conda"
    assert loaded.environment.name == "demo-env"
