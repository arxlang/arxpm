"""
title: Tests for project workflow operations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import FakeEnvironment, FakeRunner

from arxpm.environment import EnvironmentFactory, EnvironmentRuntime
from arxpm.errors import ManifestError
from arxpm.manifest import load_manifest, save_manifest
from arxpm.models import BuildConfig, DependencyGroupInclude, Manifest
from arxpm.project import ProjectService


def _factory(env: FakeEnvironment) -> EnvironmentFactory:
    def _build(manifest: Manifest, project_dir: Path) -> EnvironmentRuntime:
        _ = manifest, project_dir
        return env

    return _build


def test_init_and_add_dependency_forms(tmp_path: Path) -> None:
    service = ProjectService(environment_factory=_factory(FakeEnvironment()))

    service.init(tmp_path, name="demo")
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


def test_build_and_run_invoke_compiler_directly(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    build_result = service.build(tmp_path)
    run_result = service.run(tmp_path)

    assert build_result.artifact == tmp_path / "build" / "demo"
    assert runner.calls[0][0][:3] == [
        "arx",
        "src/demo/main.x",
        "--output-file",
    ]
    assert runner.calls[-1][0] == ["build/demo"]
    assert run_result.build_result.artifact == tmp_path / "build" / "demo"


def test_install_calls_environment_ensure_ready(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    service.install(tmp_path)

    assert env.ensure_ready_calls == 1


def test_install_dispatches_dependencies_through_environment(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    service.add_dependency(tmp_path, "http")
    service.add_dependency(
        tmp_path, "utils", git="https://example.com/utils.git"
    )

    service.install(tmp_path)

    requirements = [call[0] for call in env.install_calls]
    assert requirements == [
        ("http", "git+https://example.com/utils.git"),
    ]


def test_install_includes_selected_dependency_groups(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {
        "lint": ("ruff",),
        "Dev_Test": (DependencyGroupInclude("lint"), "pytest"),
    }
    save_manifest(tmp_path, manifest)

    service.install(tmp_path, groups=("dev-test",))

    requirements = [call[0] for call in env.install_calls]
    assert requirements == [("pytest", "ruff")]


def test_install_dev_alias_selects_dev_group(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {"dev": ("pytest",)}
    save_manifest(tmp_path, manifest)

    service.install(tmp_path, dev=True)

    requirements = [call[0] for call in env.install_calls]
    assert requirements == [("pytest",)]


def test_publish_builds_and_uploads_artifacts(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

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

    commands = [call[0] for call in runner.calls]
    assert commands[0][:3] == [sys.executable, "-m", "build"]
    upload_command = commands[1]
    assert upload_command[:4] == [sys.executable, "-m", "twine", "upload"]
    assert "--repository-url" in upload_command
    assert "--skip-existing" in upload_command
    # publish must not install build/twine into the environment.
    assert env.install_calls == []


def test_pack_builds_artifacts_without_upload(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    pack_result = service.pack(tmp_path)

    assert [path.name for path in pack_result.artifacts] == [
        "demo-0.1.0-py3-none-any.whl",
        "demo-0.1.0.tar.gz",
    ]
    assert pack_result.upload_result is None
    assert len(runner.calls) == 1


def test_publish_dry_run_skips_upload(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    publish_result = service.publish(tmp_path, dry_run=True)

    assert publish_result.upload_result is None
    assert len(runner.calls) == 1


def test_install_requires_arxproject_manifest(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))

    with pytest.raises(ManifestError):
        service.install(tmp_path)


def test_init_is_idempotent_when_manifest_exists(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))

    service.init(tmp_path, name="demo")
    main_path = tmp_path / "src" / "demo" / "main.x"
    main_path.write_text("// existing source\n", encoding="utf-8")

    second = service.init(tmp_path, name="ignored")

    assert second.project.name == "demo"
    assert main_path.read_text(encoding="utf-8") == "// existing source\n"


def test_install_packs_and_symlinks_arx_path_dependency(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    library_dir = tmp_path / "mylib"
    consumer_dir = tmp_path / "app"
    fake_install_dir = tmp_path / "fake-site-packages" / "mylib"
    fake_install_dir.mkdir(parents=True)
    (fake_install_dir / "__init__.x").write_text("", encoding="utf-8")

    runner = FakeRunner(module_install_dirs={"mylib": fake_install_dir})
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )

    service.init(library_dir, name="mylib")
    library_manifest = load_manifest(library_dir)
    library_manifest.build = BuildConfig(
        src_dir=library_manifest.build.src_dir,
        out_dir=library_manifest.build.out_dir,
        package=library_manifest.build.package,
        mode="lib",
    )
    save_manifest(library_dir, library_manifest)
    (library_dir / "src" / "mylib" / "main.x").unlink()
    service.init(consumer_dir, name="app")
    service.add_dependency(consumer_dir, "mylib", path=Path("../mylib"))

    service.install(consumer_dir)

    wheel_install_calls = [
        call
        for call in env.install_calls
        if any(req.endswith(".whl") for req in call[0])
    ]
    assert wheel_install_calls, (
        "expected environment.install_packages to be called with the wheel"
    )
    assert wheel_install_calls[0][1] is True  # force_reinstall
    assert wheel_install_calls[0][2] is True  # no_deps

    probe_commands = [
        cmd
        for cmd, _cwd, _check in runner.calls
        if len(cmd) >= 3 and cmd[1] == "-c" and "import mylib" in cmd[2]
    ]
    assert probe_commands, "expected a python -c probe for the install dir"

    symlink = consumer_dir / "mylib"
    assert symlink.is_symlink()
    assert symlink.resolve() == fake_install_dir


def test_install_rejects_arx_path_dep_name_mismatch(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))

    library_dir = tmp_path / "weird_dir_name"
    consumer_dir = tmp_path / "app"
    service.init(library_dir, name="actual_module")
    library_manifest = load_manifest(library_dir)
    library_manifest.build = BuildConfig(
        src_dir=library_manifest.build.src_dir,
        out_dir=library_manifest.build.out_dir,
        package=library_manifest.build.package,
        mode="lib",
    )
    save_manifest(library_dir, library_manifest)
    (library_dir / "src" / "actual_module" / "main.x").unlink()
    service.init(consumer_dir, name="app")
    service.add_dependency(
        consumer_dir,
        "declared_name",
        path=Path("../weird_dir_name"),
    )

    with pytest.raises(ManifestError, match="must match the library"):
        service.install(consumer_dir)


def test_install_rejects_unknown_dependency_group(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    with pytest.raises(ManifestError, match="unknown dependency group"):
        service.install(tmp_path, groups=("docs",))


def test_save_manifest_rejects_dependency_group_include_cycles(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {
        "dev": (DependencyGroupInclude("lint"),),
        "lint": (DependencyGroupInclude("dev"),),
    }

    with pytest.raises(ManifestError, match="must not form cycles"):
        save_manifest(tmp_path, manifest)


def test_install_rejects_conflicts_between_base_and_group_dependencies(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")
    service.add_dependency(tmp_path, "http")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {
        "dev": ("http @ ../http-local",),
    }
    save_manifest(tmp_path, manifest)

    with pytest.raises(ManifestError, match="defines conflicting entries"):
        service.install(tmp_path, groups=("dev",))


def test_install_rejects_conflicts_across_included_groups(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {
        "lint": ("ruff",),
        "docs": ("ruff @ ../ruff-local",),
        "dev": (
            DependencyGroupInclude("lint"),
            DependencyGroupInclude("docs"),
        ),
    }
    save_manifest(tmp_path, manifest)

    with pytest.raises(ManifestError, match="defines conflicting entries"):
        service.install(tmp_path, groups=("dev",))


def test_build_uses_init_module_for_lib_projects(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.build = BuildConfig(
        src_dir=manifest.build.src_dir,
        out_dir=manifest.build.out_dir,
        package=manifest.build.package,
        mode="lib",
    )
    save_manifest(tmp_path, manifest)
    (tmp_path / "src" / "demo" / "main.x").unlink()

    build_result = service.build(tmp_path)

    assert build_result.artifact == tmp_path / "build" / "demo"
    assert runner.calls[0][0] == [
        "arx",
        "src/demo/__init__.x",
        "--output-file",
        "build/demo",
    ]


def test_run_rejects_lib_projects(tmp_path: Path) -> None:
    service = ProjectService(environment_factory=_factory(FakeEnvironment()))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.build = BuildConfig(
        src_dir=manifest.build.src_dir,
        out_dir=manifest.build.out_dir,
        package=manifest.build.package,
        mode="lib",
    )
    save_manifest(tmp_path, manifest)
    (tmp_path / "src" / "demo" / "main.x").unlink()

    with pytest.raises(ManifestError, match="only available for app projects"):
        service.run(tmp_path)
