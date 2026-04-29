"""
title: Tests for project workflow operations.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from conftest import FakeEnvironment, FakeRunner

from arxpm.environment import EnvironmentFactory, EnvironmentRuntime
from arxpm.errors import EnvironmentError, ManifestError
from arxpm.external import CommandResult
from arxpm.manifest import load_manifest, save_manifest
from arxpm.models import (
    BuildConfig,
    BuildSystemConfig,
    DependencyGroupInclude,
    DependencySpec,
    Manifest,
)
from arxpm.project import ProjectService, _prepare_publish_workspace


def _factory(env: FakeEnvironment) -> EnvironmentFactory:
    def _build(manifest: Manifest, project_dir: Path) -> EnvironmentRuntime:
        _ = manifest, project_dir
        return env

    return _build


def _assert_default_arx_requirement(requirement: str) -> None:
    assert requirement.startswith("arxlang>=")


class FakeCredentialStore:
    """
    title: Publish credential provider test double.
    attributes:
      tokens:
        type: dict[str, str]
      calls:
        type: list[str]
    """

    tokens: dict[str, str]
    calls: list[str]

    def __init__(self, tokens: dict[str, str] | None = None) -> None:
        self.tokens = tokens or {}
        self.calls = []

    def get_token(self, repository: str) -> str | None:
        self.calls.append(repository)
        return self.tokens.get(repository)


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


def test_build_and_run_invoke_environment_arx_executable(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment(tmp_path / ".venv" / "bin" / "python")
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
    )
    service.init(tmp_path, name="demo")

    build_result = service.build(tmp_path)
    run_result = service.run(tmp_path)

    assert build_result.artifact == tmp_path / "build" / "demo"
    assert runner.calls[0][0][:2] == [
        str(tmp_path / ".venv" / "bin" / "arx"),
        "src/demo/main.x",
    ]
    assert runner.calls[-1][0] == ["build/demo"]
    assert run_result.build_result.artifact == tmp_path / "build" / "demo"


def test_build_reports_missing_environment_compiler_before_install(
    tmp_path: Path,
) -> None:
    def runner(
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        _ = cwd, check, env
        raise FileNotFoundError(command[0])

    service = ProjectService(runner=runner)
    service.init(tmp_path, name="demo")

    with pytest.raises(
        EnvironmentError,
        match=r"arx compiler not found .*run arxpm install",
    ):
        service.build(tmp_path)


def test_install_calls_environment_ensure_ready(tmp_path: Path) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    service.install(tmp_path)

    assert env.ensure_ready_calls == 1
    assert len(env.install_calls) == 1
    assert env.install_calls[0][1:] == (False, False)
    _assert_default_arx_requirement(env.install_calls[0][0][0])


def test_install_preserves_explicit_arx_build_dependency(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")
    manifest = load_manifest(tmp_path)
    manifest.build_system = BuildSystemConfig(dependencies=("arxlang==1.5.0",))
    save_manifest(tmp_path, manifest)

    service.install(tmp_path)

    assert env.install_calls == [(("arxlang==1.5.0",), False, False)]


def test_install_dispatches_dependencies_through_environment(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    service.add_dependency(tmp_path, "http")
    service.add_dependency(
        tmp_path, "utils", git="https://example.com/utils.git"
    )

    service.install(tmp_path)

    requirements = [call[0] for call in env.install_calls]
    assert len(requirements) == 1
    _assert_default_arx_requirement(requirements[0][0])
    assert requirements[0][1:] == (
        "http",
        "git+https://example.com/utils.git",
    )
    assert not (tmp_path / "http").exists()
    assert not (tmp_path / "utils").exists()


def test_install_uses_project_dependency_version_constraints(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependencies["http"] = DependencySpec.registry(">=1.2")
    save_manifest(tmp_path, manifest)

    service.install(tmp_path)

    requirements = env.install_calls[0][0]
    _assert_default_arx_requirement(requirements[0])
    assert requirements[1:] == ("http>=1.2",)


def test_install_includes_selected_dependency_groups(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {
        "lint": ("ruff",),
        "Dev_Test": (DependencyGroupInclude("lint"), "pytest"),
    }
    save_manifest(tmp_path, manifest)

    service.install(tmp_path, groups=("dev-test",))

    requirements = [call[0] for call in env.install_calls]
    assert len(requirements) == 1
    _assert_default_arx_requirement(requirements[0][0])
    assert requirements[0][1:] == ("pytest", "ruff")


def test_install_dev_alias_selects_dev_group(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(tmp_path, name="demo")

    manifest = load_manifest(tmp_path)
    manifest.dependency_groups = {"dev": ("pytest",)}
    save_manifest(tmp_path, manifest)

    service.install(tmp_path, dev=True)

    requirements = [call[0] for call in env.install_calls]
    assert len(requirements) == 1
    _assert_default_arx_requirement(requirements[0][0])
    assert requirements[0][1:] == ("pytest",)


def test_publish_builds_and_uploads_artifacts(tmp_path: Path) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
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
    assert "--sdist" in commands[0]
    assert "--wheel" in commands[0]
    upload_command = commands[1]
    assert upload_command[:4] == [sys.executable, "-m", "twine", "upload"]
    assert "--repository-url" in upload_command
    assert "--skip-existing" in upload_command
    # publish must not install build/twine into the environment.
    assert env.install_calls == []


def test_publish_maps_namespaced_token_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARXPM_PUBLISH_TOKEN", "pypi-token")
    monkeypatch.setenv(
        "ARXPM_PUBLISH_REPOSITORY_URL",
        "https://test.pypi.org/legacy/",
    )
    monkeypatch.setenv("TWINE_USERNAME", "backend-user")
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
    )
    service.init(tmp_path, name="demo")

    service.publish(tmp_path)

    upload_command = runner.calls[1][0]
    upload_environment = runner.environments[1]
    assert upload_environment is not None
    assert upload_environment["TWINE_USERNAME"] == "__token__"
    assert upload_environment["TWINE_PASSWORD"] == "pypi-token"
    assert (
        upload_environment["TWINE_REPOSITORY_URL"]
        == "https://test.pypi.org/legacy/"
    )
    assert "pypi-token" not in upload_command
    assert "backend-user" not in upload_environment.values()


def test_publish_maps_namespaced_username_and_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARXPM_PUBLISH_USERNAME", "demo-user")
    monkeypatch.setenv("ARXPM_PUBLISH_PASSWORD", "demo-password")
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
    )
    service.init(tmp_path, name="demo")

    service.publish(tmp_path)

    upload_environment = runner.environments[1]
    assert upload_environment is not None
    assert upload_environment["TWINE_USERNAME"] == "demo-user"
    assert upload_environment["TWINE_PASSWORD"] == "demo-password"


def test_publish_uses_stored_pypi_token_by_default(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    credentials = FakeCredentialStore({"pypi": "stored-token"})
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=credentials,
    )
    service.init(tmp_path, name="demo")

    service.publish(tmp_path)

    upload_environment = runner.environments[1]
    assert upload_environment is not None
    assert credentials.calls == ["pypi"]
    assert upload_environment["TWINE_USERNAME"] == "__token__"
    assert upload_environment["TWINE_PASSWORD"] == "stored-token"


def test_publish_uses_stored_testpypi_token_for_testpypi_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARXPM_PUBLISH_REPOSITORY_URL",
        "https://test.pypi.org/legacy/",
    )
    env = FakeEnvironment()
    runner = FakeRunner()
    credentials = FakeCredentialStore({"testpypi": "stored-test-token"})
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=credentials,
    )
    service.init(tmp_path, name="demo")

    service.publish(tmp_path)

    upload_environment = runner.environments[1]
    assert upload_environment is not None
    assert credentials.calls == ["testpypi"]
    assert upload_environment["TWINE_PASSWORD"] == "stored-test-token"


def test_publish_does_not_use_stored_token_for_custom_repository(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    runner = FakeRunner()
    credentials = FakeCredentialStore({"pypi": "stored-token"})
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=credentials,
    )
    service.init(tmp_path, name="demo")

    service.publish(
        tmp_path,
        repository_url="https://packages.example.com/legacy/",
    )

    upload_environment = runner.environments[1]
    assert upload_environment is not None
    assert credentials.calls == []
    assert "TWINE_PASSWORD" not in upload_environment


def test_publish_rejects_empty_namespaced_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARXPM_PUBLISH_TOKEN", " ")
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
    )
    service.init(tmp_path, name="demo")

    with pytest.raises(
        ManifestError,
        match="ARXPM_PUBLISH_TOKEN cannot be empty",
    ):
        service.publish(tmp_path)

    assert runner.calls == []


def test_publish_rejects_token_with_basic_auth_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARXPM_PUBLISH_TOKEN", "pypi-token")
    monkeypatch.setenv("ARXPM_PUBLISH_USERNAME", "demo-user")
    env = FakeEnvironment()
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
        credential_store=FakeCredentialStore(),
    )
    service.init(tmp_path, name="demo")

    with pytest.raises(ManifestError, match="cannot be combined"):
        service.publish(tmp_path)

    assert runner.calls == []


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
    assert "--sdist" in runner.calls[0][0]
    assert "--wheel" in runner.calls[0][0]


def test_publish_workspace_renders_dependency_metadata(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    service = ProjectService(environment_factory=_factory(env))
    service.init(tmp_path, name="demo")
    service.add_dependency(tmp_path, "http>=1.2")
    service.add_dependency(tmp_path, "local-lib", path=Path("../local-lib"))
    service.add_dependency(
        tmp_path,
        "utils",
        git="https://example.com/utils.git",
    )

    staging_dir = tmp_path / "staging"
    _prepare_publish_workspace(
        tmp_path,
        load_manifest(tmp_path),
        staging_dir,
    )

    pyproject_text = (staging_dir / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "dependencies = [" in pyproject_text
    assert '  "http>=1.2",' in pyproject_text
    assert '  "local-lib",' in pyproject_text
    assert '  "utils @ git+https://example.com/utils.git",' in pyproject_text


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


def test_install_packs_arx_path_dependency_without_source_link(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    library_dir = tmp_path / "mylib"
    consumer_dir = tmp_path / "app"

    runner = FakeRunner()
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

    assert env.install_calls[0][1:] == (False, False)
    _assert_default_arx_requirement(env.install_calls[0][0][0])
    assert not (consumer_dir / "mylib").exists()


def test_install_leaves_installed_registry_arx_dependency_unlinked(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    consumer_dir = tmp_path / "app"
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(consumer_dir, name="app")
    service.add_dependency(consumer_dir, "shared-lib")

    service.install(consumer_dir)

    assert len(env.install_calls) == 1
    _assert_default_arx_requirement(env.install_calls[0][0][0])
    assert env.install_calls[0][0][1:] == ("shared-lib",)
    assert env.install_calls[0][1:] == (False, False)
    assert not (consumer_dir / "shared_lib").exists()


def test_install_delegates_transitive_registry_arx_dependencies_to_uv(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    consumer_dir = tmp_path / "app"
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(consumer_dir, name="app")
    service.add_dependency(consumer_dir, "project-a")

    service.install(consumer_dir)

    assert len(env.install_calls) == 1
    _assert_default_arx_requirement(env.install_calls[0][0][0])
    assert env.install_calls[0][0][1:] == ("project-a",)
    assert env.install_calls[0][1:] == (False, False)
    assert not (consumer_dir / "project_a").exists()
    assert not (consumer_dir / "project_b").exists()


def test_install_packs_nested_arx_path_dependency(
    tmp_path: Path,
) -> None:
    env = FakeEnvironment()
    consumer_dir = tmp_path / "app"
    project_a_dir = tmp_path / "project_a"
    project_b_dir = tmp_path / "project_b"
    runner = FakeRunner()
    service = ProjectService(
        environment_factory=_factory(env),
        runner=runner,
    )
    service.init(project_b_dir, name="project_b")
    project_b_manifest = load_manifest(project_b_dir)
    project_b_manifest.build = BuildConfig(
        src_dir=project_b_manifest.build.src_dir,
        out_dir=project_b_manifest.build.out_dir,
        package=project_b_manifest.build.package,
        mode="lib",
    )
    save_manifest(project_b_dir, project_b_manifest)
    (project_b_dir / "src" / "project_b" / "main.x").unlink()

    service.init(project_a_dir, name="project_a")
    project_a_manifest = load_manifest(project_a_dir)
    project_a_manifest.build = BuildConfig(
        src_dir=project_a_manifest.build.src_dir,
        out_dir=project_a_manifest.build.out_dir,
        package=project_a_manifest.build.package,
        mode="lib",
    )
    save_manifest(project_a_dir, project_a_manifest)
    (project_a_dir / "src" / "project_a" / "main.x").unlink()
    service.add_dependency(
        project_a_dir,
        "project_b",
        path=Path("../project_b"),
    )

    service.init(consumer_dir, name="app")
    service.add_dependency(
        consumer_dir,
        "project_a",
        path=Path("../project_a"),
    )

    service.install(consumer_dir)

    wheel_installs = [
        call[0][0]
        for call in env.install_calls
        if call[0] and call[0][0].endswith(".whl")
    ]
    assert any("project_b" in wheel for wheel in wheel_installs)
    assert any("project_a" in wheel for wheel in wheel_installs)
    assert env.install_calls[0][1:] == (False, False)
    _assert_default_arx_requirement(env.install_calls[0][0][0])
    assert not (consumer_dir / "project_a").exists()
    assert not (consumer_dir / "project_b").exists()


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
        "/fake/arx",
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
