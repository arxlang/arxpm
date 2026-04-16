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
    assert loaded.build.entry == "src/main.x"
    assert loaded.toolchain.linker == "clang"


def test_manifest_parses_all_dependency_forms(tmp_path: Path) -> None:
    content = """
[project]
name = "hello-arx"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
out_dir = "build"

[dependencies]
http = { source = "registry" }
mylib = { path = "../mylib" }
utils = { git = "https://example.com/utils.git" }

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


def test_manifest_rejects_invalid_dependency_value(tmp_path: Path) -> None:
    content = """
[project]
name = "bad"
version = "0.1.0"
edition = "2026"

[build]
entry = "src/main.x"
out_dir = "build"

[dependencies]
http = "oops"

[toolchain]
compiler = "arx"
linker = "clang"
""".strip()
    path = tmp_path / ".arxproject.toml"
    path.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(ManifestError):
        load_manifest_file(path)
