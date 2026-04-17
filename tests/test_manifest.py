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
