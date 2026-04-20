"""
title: Tests for manifest and model invariants.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from arxpm.errors import ManifestError
from arxpm.models import (
    BuildConfig,
    DependencyGroupInclude,
    DependencySpec,
    EnvironmentConfig,
    Manifest,
    ProjectConfig,
    ToolchainConfig,
)


def test_environment_config_default_and_resolved_path() -> None:
    config = EnvironmentConfig.default()

    assert config.is_default() is True
    assert config.resolved_path() == ".venv"


def test_environment_config_non_default_venv_path() -> None:
    config = EnvironmentConfig(kind="venv", path=".custom-venv")

    assert config.is_default() is False
    assert config.resolved_path() == ".custom-venv"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"kind": "bogus"}, "environment.kind must be one of"),
        (
            {"kind": "venv", "path": "   "},
            "environment.path must be a non-empty string",
        ),
        (
            {"kind": "venv", "name": "named"},
            "environment.name is not allowed when kind is 'venv'",
        ),
        (
            {"kind": "conda"},
            "environment requires 'name' or 'path' when kind is 'conda'",
        ),
        (
            {"kind": "system", "path": "/usr/bin/python"},
            "environment.path and environment.name are not allowed",
        ),
        (
            {"kind": "system", "name": "base"},
            "environment.path and environment.name are not allowed",
        ),
    ],
)
def test_environment_config_rejects_invalid_values(
    kwargs: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        EnvironmentConfig(**kwargs)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: ProjectConfig(name=""),
            "project.name must be a non-empty string",
        ),
        (
            lambda: ProjectConfig(name="demo", version=""),
            "project.version must be a non-empty string",
        ),
        (
            lambda: ProjectConfig(name="demo", edition=""),
            "project.edition must be a non-empty string",
        ),
        (
            lambda: BuildConfig(src_dir=""),
            "build.src_dir must be a non-empty string",
        ),
        (
            lambda: BuildConfig(package=""),
            "build.package must be a non-empty string",
        ),
        (
            lambda: BuildConfig(mode="cli"),
            "build.mode must be 'lib' or 'app'",
        ),
        (
            lambda: BuildConfig(out_dir=""),
            "build.out_dir must be a non-empty string",
        ),
        (
            lambda: ToolchainConfig(compiler=""),
            "toolchain.compiler must be a non-empty string",
        ),
        (
            lambda: ToolchainConfig(linker=""),
            "toolchain.linker must be a non-empty string",
        ),
    ],
)
def test_project_build_and_toolchain_reject_blank_values(
    factory: Callable[[], object],
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        factory()


def test_manifest_from_dict_applies_build_defaults() -> None:
    manifest = Manifest.from_dict(
        {
            "project": {
                "name": "demo",
                "version": "0.1.0",
            }
        }
    )

    assert manifest.build.src_dir == "src"
    assert manifest.build.out_dir == "build"
    assert manifest.build.package is None
    assert manifest.build.mode is None


@pytest.mark.parametrize(
    ("spec", "kind"),
    [
        (DependencySpec.registry(), "registry"),
        (DependencySpec.from_path("../pkg"), "path"),
        (DependencySpec.from_git("https://example.com/repo.git"), "git"),
    ],
)
def test_dependency_spec_kind_reports_source(
    spec: DependencySpec,
    kind: str,
) -> None:
    assert spec.kind == kind


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "dependency must define exactly one of source, path, or git"),
        (
            {"source": "registry", "path": "../pkg"},
            "dependency must define exactly one of source, path, or git",
        ),
        ({"source": "custom"}, "dependency source must be 'registry' in v0"),
        ({"path": "   "}, "dependency path must be non-empty"),
        ({"git": "   "}, "dependency git must be non-empty"),
    ],
)
def test_dependency_spec_rejects_invalid_shapes(
    kwargs: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        DependencySpec(**kwargs)


@pytest.mark.parametrize(
    ("requirement", "name", "kind", "value"),
    [
        ("http", "http", "registry", None),
        ("mylib @ ../mylib", "mylib", "path", "../mylib"),
        (
            "utils @ git+https://example.com/utils.git",
            "utils",
            "git",
            "https://example.com/utils.git",
        ),
    ],
)
def test_dependency_spec_parse_requirement_accepts_supported_forms(
    requirement: str,
    name: str,
    kind: str,
    value: str | None,
) -> None:
    parsed_name, spec = DependencySpec.parse_requirement(requirement)

    assert parsed_name == name
    assert spec.kind == kind
    if kind == "path":
        assert spec.path == value
    if kind == "git":
        assert spec.git == value


@pytest.mark.parametrize(
    ("requirement", "message"),
    [
        ("", "dependency entry must be a non-empty string"),
        ("pkg @", "must specify a reference after '@'"),
        ("1bad", "dependency name"),
        (" @ ../pkg", "missing a name before"),
    ],
)
def test_dependency_spec_parse_requirement_rejects_invalid_forms(
    requirement: str,
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        DependencySpec.parse_requirement(requirement)


def test_manifest_from_dict_applies_defaults_and_to_dict_round_trips() -> None:
    manifest = Manifest.from_dict(
        {
            "project": {
                "name": "demo",
                "version": "0.1.0",
            }
        }
    )

    assert manifest.toolchain.compiler == "arx"
    assert manifest.environment.is_default() is True
    assert manifest.to_dict()["project"]["dependencies"] == []
    assert manifest.to_dict()["build"] == {
        "src_dir": "src",
        "out_dir": "build",
    }


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (
            {"dependencies": {}},
            r"top-level \[dependencies\] table is no longer supported",
        ),
        ({"build": []}, "build must be a table"),
        (
            {"build": {"entry": "src/main.x"}},
            r"\[build\]\.entry is no longer supported",
        ),
        ({"toolchain": []}, "toolchain must be a table"),
        ({"environment": []}, "environment must be a table"),
        ({"extra": {}}, "manifest has unknown top-level keys: extra"),
    ],
)
def test_manifest_from_dict_rejects_invalid_top_level_shapes(
    raw: dict[str, object],
    message: str,
) -> None:
    payload: dict[str, object] = {
        "project": {
            "name": "demo",
            "version": "0.1.0",
        }
    }
    payload.update(raw)

    with pytest.raises(ManifestError, match=message):
        Manifest.from_dict(payload)


@pytest.mark.parametrize(
    ("dependencies", "message"),
    [
        ("http", "project.dependencies must be an array of strings"),
        (
            {"http": "registry"},
            "project.dependencies must be an array of strings",
        ),
        (["http", "http"], "contains duplicate entry"),
    ],
)
def test_manifest_from_dict_rejects_invalid_project_dependencies(
    dependencies: object,
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        Manifest.from_dict(
            {
                "project": {
                    "name": "demo",
                    "version": "0.1.0",
                    "dependencies": dependencies,
                }
            }
        )


def test_manifest_from_dict_parses_package_and_mode() -> None:
    manifest = Manifest.from_dict(
        {
            "project": {
                "name": "my-project",
                "version": "0.1.0",
            },
            "build": {
                "package": "my_project",
                "mode": "lib",
            },
        }
    )

    assert manifest.build.package == "my_project"
    assert manifest.build.mode == "lib"


def test_manifest_from_dict_parses_dependency_groups_and_environment() -> None:
    manifest = Manifest.from_dict(
        {
            "project": {
                "name": "demo",
                "version": "0.1.0",
                "dependencies": ["http"],
            },
            "dependency-groups": {
                "lint": ["ruff"],
                "Dev_Test": [
                    {"include-group": "lint"},
                    "pytest",
                ],
            },
            "environment": {
                "kind": "conda",
                "name": "demo-env",
            },
        }
    )

    assert manifest.dependencies["http"] == DependencySpec.registry()
    assert manifest.environment.kind == "conda"
    entries = manifest.dependency_groups["Dev_Test"]
    assert entries[0] == DependencyGroupInclude("lint")
    assert entries[1] == "pytest"


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        (
            {"dev-test": [], "dev_test": []},
            "must be unique after normalization",
        ),
        ({"dev": [{"include-group": "missing"}]}, "includes unknown group"),
        ({1: []}, "dependency-groups keys must be strings"),
        (
            {"bad name": []},
            r"must match \[A-Za-z0-9\]\[A-Za-z0-9._-\]\*",
        ),
        ({"dev": "pytest"}, "dependency-groups.dev must be an array"),
        ({"dev": [1]}, "must be a string or "),
        ({"dev": [{"wrong-key": "lint"}]}, "must only use include-group"),
        ({"dev": [{"include-group": 1}]}, "include-group must be a string"),
    ],
)
def test_manifest_from_dict_rejects_invalid_dependency_groups(
    groups: object,
    message: str,
) -> None:
    with pytest.raises(ManifestError, match=message):
        Manifest.from_dict(
            {
                "project": {
                    "name": "demo",
                    "version": "0.1.0",
                },
                "dependency-groups": groups,
            }
        )
