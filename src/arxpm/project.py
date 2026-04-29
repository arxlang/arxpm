"""
title: Project lifecycle operations.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from arxpm.credentials import (
    PublishCredentialProvider,
    PublishCredentialStore,
)
from arxpm.environment import (
    EnvironmentFactory,
    EnvironmentRuntime,
    build_environment,
    environment_executable,
)
from arxpm.errors import EnvironmentError, ManifestError
from arxpm.external import CommandResult, CommandRunner, run_command
from arxpm.layout import (
    ResolvedBuildConfig,
    is_valid_package_name,
    resolve_build_config,
)
from arxpm.manifest import (
    MANIFEST_FILENAME,
    create_default_manifest,
    load_manifest,
    render_manifest,
    save_manifest,
)
from arxpm.models import (
    BuildConfig,
    DependencyGroupInclude,
    DependencySpec,
    EnvironmentConfig,
    Manifest,
    effective_build_system_dependencies,
)

_INIT_SOURCE = """```
title: Package root module
```
"""

_MAIN_SOURCE = """```
title: Simple main module
```

fn main() -> i32:
  ```
  title: Print hello world
  returns:
    type: i32
  ```
  print("Hello, Arx!")
  return 0
"""

_SOURCE_SUFFIXES = (".x", ".arx")
PUBLISH_DEFAULT_REPOSITORY_URL = "https://upload.pypi.org/legacy/"
PUBLISH_TEST_REPOSITORY_URL = "https://test.pypi.org/legacy/"
_PUBLISH_TOKEN_USERNAME = "__token__"
_PUBLISH_ENV_TOKEN = "ARXPM_PUBLISH_TOKEN"
_PUBLISH_ENV_USERNAME = "ARXPM_PUBLISH_USERNAME"
_PUBLISH_ENV_PASSWORD = "ARXPM_PUBLISH_PASSWORD"
_PUBLISH_ENV_REPOSITORY_URL = "ARXPM_PUBLISH_REPOSITORY_URL"
_PUBLISH_BACKEND_ENV_PREFIX = "TWINE_"
_PUBLISH_BACKEND_USERNAME = "TWINE_USERNAME"
_PUBLISH_BACKEND_PASSWORD = "TWINE_PASSWORD"
_PUBLISH_BACKEND_REPOSITORY_URL = "TWINE_REPOSITORY_URL"
_EXCLUDED_SOURCE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
_DEFAULT_ARX_COMPILER = "arx"


@dataclass(slots=True, frozen=True)
class BuildResult:
    """
    title: Build execution output.
    attributes:
      manifest:
        type: Manifest
      layout:
        type: ResolvedBuildConfig
      command_result:
        type: CommandResult
      artifact:
        type: Path
    """

    manifest: Manifest
    layout: ResolvedBuildConfig
    command_result: CommandResult
    artifact: Path


@dataclass(slots=True, frozen=True)
class RunResult:
    """
    title: Run execution output.
    attributes:
      build_result:
        type: BuildResult
      command_result:
        type: CommandResult
    """

    build_result: BuildResult
    command_result: CommandResult


@dataclass(slots=True, frozen=True)
class PublishResult:
    """
    title: Publish execution output.
    attributes:
      manifest:
        type: Manifest
      artifacts:
        type: tuple[Path, Ellipsis]
      upload_result:
        type: CommandResult | None
    """

    manifest: Manifest
    artifacts: tuple[Path, ...]
    upload_result: CommandResult | None


class ProjectService:
    """
    title: High-level project workflows.
    attributes:
      _environment_factory:
        type: EnvironmentFactory
      _runner:
        type: CommandRunner
      _credential_store:
        type: PublishCredentialProvider
    """

    _environment_factory: EnvironmentFactory
    _runner: CommandRunner
    _credential_store: PublishCredentialProvider

    def __init__(
        self,
        environment_factory: EnvironmentFactory | None = None,
        runner: CommandRunner = run_command,
        credential_store: PublishCredentialProvider | None = None,
    ) -> None:
        self._environment_factory = environment_factory or build_environment
        self._runner = runner
        self._credential_store = credential_store or PublishCredentialStore()

    def init(
        self,
        directory: Path,
        name: str | None = None,
        environment: EnvironmentConfig | None = None,
    ) -> Manifest:
        """
        title: Initialize a new Arx project.
        parameters:
          directory:
            type: Path
          name:
            type: str | None
          environment:
            type: EnvironmentConfig | None
        returns:
          type: Manifest
        """
        project_name = name or directory.resolve().name
        manifest_path = directory / MANIFEST_FILENAME
        if manifest_path.exists():
            manifest = load_manifest(directory)
        else:
            manifest = create_default_manifest(project_name)
            package_name = (
                _arx_module_name(manifest.project.name)
                if not is_valid_package_name(manifest.project.name)
                else None
            )
            manifest.build = BuildConfig(
                src_dir=manifest.build.src_dir,
                out_dir=manifest.build.out_dir,
                package=package_name,
                mode="app",
            )
            if environment is not None:
                manifest.environment = environment
            save_manifest(directory, manifest)

        package_name = manifest.build.package or manifest.project.name
        source_root = directory / manifest.build.src_dir
        package_root = source_root / package_name
        init_path = package_root / "__init__.x"
        main_path = package_root / "main.x"

        package_root.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            init_path.write_text(_INIT_SOURCE, encoding="utf-8")

        mode = manifest.build.mode
        if mode == "app" or (mode is None and not main_path.exists()):
            if not main_path.exists():
                main_path.write_text(_MAIN_SOURCE, encoding="utf-8")

        return manifest

    def add_dependency(
        self,
        directory: Path,
        name: str,
        path: Path | None = None,
        git: str | None = None,
    ) -> Manifest:
        """
        title: Add or update a dependency in .arxproject.toml.
        parameters:
          directory:
            type: Path
          name:
            type: str
          path:
            type: Path | None
          git:
            type: str | None
        returns:
          type: Manifest
        """
        if not name.strip():
            raise ManifestError("dependency name must be a non-empty string")
        if path is not None and git is not None:
            raise ManifestError("use either --path or --git, not both")

        manifest = load_manifest(directory)

        spec: DependencySpec
        if path is not None:
            dependency_name = _parse_bare_dependency_name(name)
            spec = DependencySpec.from_path(str(path))
        elif git is not None:
            dependency_name = _parse_bare_dependency_name(name)
            spec = DependencySpec.from_git(git)
        else:
            dependency_name, spec = DependencySpec.parse_requirement(name)

        manifest.dependencies[dependency_name] = spec
        save_manifest(directory, manifest)
        return manifest

    def install(
        self,
        directory: Path,
        groups: Sequence[str] = (),
        dev: bool = False,
    ) -> CommandResult:
        """
        title: Install or sync environment dependencies.
        parameters:
          directory:
            type: Path
          groups:
            type: Sequence[str]
          dev:
            type: bool
        returns:
          type: CommandResult
        """
        manifest = load_manifest(directory)
        environment = self._environment_factory(manifest, directory)
        environment.ensure_ready()

        selected_groups = list(groups)
        if dev:
            selected_groups.append("dev")

        dependencies = dict(manifest.dependencies)
        if selected_groups:
            grouped_dependencies = _resolve_dependency_group_dependencies(
                manifest,
                selected_groups,
            )
            dependencies = _merge_dependency_maps(
                dependencies,
                grouped_dependencies,
                label="selected dependency groups",
            )

        registry_reqs, path_deps = _partition_dependencies(
            directory,
            dependencies,
        )
        install_reqs = _environment_install_requirements(
            manifest,
            registry_reqs,
        )
        command_result = environment.install_packages(install_reqs)
        installing_path_deps: list[Path] = []
        installed_path_deps: set[Path] = set()
        for dependency_name, library_directory in path_deps:
            self._install_arx_path_dependency(
                directory,
                environment,
                dependency_name,
                library_directory,
                installing_path_deps,
                installed_path_deps,
            )

        return command_result

    def build(self, directory: Path) -> BuildResult:
        """
        title: Build a project by invoking the configured Arx compiler.
        parameters:
          directory:
            type: Path
        returns:
          type: BuildResult
        """
        manifest = load_manifest(directory)
        layout = resolve_build_config(manifest, directory)
        environment = self._environment_factory(manifest, directory)
        environment.validate()
        return self._build_with_layout(
            directory,
            manifest,
            layout,
            environment,
        )

    def run(self, directory: Path) -> RunResult:
        """
        title: Build and run the produced artifact.
        parameters:
          directory:
            type: Path
        returns:
          type: RunResult
        """
        manifest = load_manifest(directory)
        layout = resolve_build_config(manifest, directory)
        if layout.mode != "app":
            raise ManifestError(
                "arxpm run is only available for app projects; "
                f"resolved mode is {layout.mode!r}"
            )

        environment = self._environment_factory(manifest, directory)
        environment.validate()
        build_result = self._build_with_layout(
            directory,
            manifest,
            layout,
            environment,
        )
        artifact_rel = Path(layout.out_dir) / layout.package
        command_result = self._runner(
            [str(artifact_rel)],
            cwd=directory,
            check=True,
        )
        return RunResult(
            build_result=build_result,
            command_result=command_result,
        )

    def _build_with_layout(
        self,
        directory: Path,
        manifest: Manifest,
        layout: ResolvedBuildConfig,
        environment: EnvironmentRuntime,
    ) -> BuildResult:
        source_path = layout.target_file.relative_to(directory).as_posix()
        artifact_rel = Path(layout.out_dir) / layout.package
        artifact_path = directory / artifact_rel
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        command = _compiler_command(
            environment,
            source_path,
            artifact_rel,
        )
        try:
            command_result = self._runner(command, cwd=directory, check=True)
        except OSError as exc:
            raise EnvironmentError(
                f"arx compiler not found at {command[0]}; run arxpm install"
            ) from exc

        return BuildResult(
            manifest=manifest,
            layout=layout,
            command_result=command_result,
            artifact=artifact_path,
        )

    def pack(self, directory: Path) -> PublishResult:
        """
        title: Build package artifacts without uploading.
        parameters:
          directory:
            type: Path
        returns:
          type: PublishResult
        """
        return self.publish(directory, dry_run=True)

    def publish(
        self,
        directory: Path,
        repository_url: str | None = None,
        skip_existing: bool = False,
        dry_run: bool = False,
    ) -> PublishResult:
        """
        title: Build and publish project sources as a Python package.
        parameters:
          directory:
            type: Path
          repository_url:
            type: str | None
          skip_existing:
            type: bool
          dry_run:
            type: bool
        returns:
          type: PublishResult
        """
        manifest = load_manifest(directory)

        upload_repository_url = _normalize_publish_value(
            "repository URL",
            repository_url,
        )
        upload_environment = None
        if not dry_run:
            upload_environment = _build_publish_environment(
                os.environ,
                upload_repository_url,
                self._credential_store,
            )

        dist_dir = directory / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        artifacts_before = {
            path.resolve() for path in dist_dir.iterdir() if path.is_file()
        }

        with tempfile.TemporaryDirectory(prefix="arxpm-publish-") as temp_dir:
            staging_dir = Path(temp_dir) / "package"
            _prepare_publish_workspace(directory, manifest, staging_dir)
            self._runner(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--sdist",
                    "--wheel",
                    "--outdir",
                    str(dist_dir),
                    str(staging_dir),
                ],
                cwd=directory,
                check=True,
            )

        artifacts = tuple(
            sorted(
                (
                    path
                    for path in dist_dir.iterdir()
                    if path.is_file()
                    and path.resolve() not in artifacts_before
                ),
                key=lambda path: path.name,
            )
        )
        if not artifacts:
            raise ManifestError("publish build produced no artifacts")

        if dry_run:
            return PublishResult(
                manifest=manifest,
                artifacts=artifacts,
                upload_result=None,
            )

        upload_cmd = [
            sys.executable,
            "-m",
            "twine",
            "upload",
            "--non-interactive",
        ]
        if upload_repository_url:
            upload_cmd.extend(["--repository-url", upload_repository_url])
        if skip_existing:
            upload_cmd.append("--skip-existing")
        upload_cmd.extend(str(path) for path in artifacts)

        assert upload_environment is not None
        upload_result = self._runner(
            upload_cmd,
            cwd=directory,
            check=True,
            env=upload_environment,
        )
        return PublishResult(
            manifest=manifest,
            artifacts=artifacts,
            upload_result=upload_result,
        )

    def _install_arx_path_dependency(
        self,
        directory: Path,
        environment: EnvironmentRuntime,
        dependency_name: str,
        library_directory: Path,
        installing: list[Path] | None = None,
        installed: set[Path] | None = None,
    ) -> None:
        """
        title: Install one Arx path dependency and its dependency closure.
        parameters:
          directory:
            type: Path
          environment:
            type: EnvironmentRuntime
          dependency_name:
            type: str
          library_directory:
            type: Path
          installing:
            type: list[Path] | None
          installed:
            type: set[Path] | None
        """
        installing_stack = installing if installing is not None else []
        installed_paths = installed if installed is not None else set()
        resolved_library_directory = library_directory.resolve()
        if resolved_library_directory in installing_stack:
            cycle = " -> ".join(
                str(path) for path in [*installing_stack, library_directory]
            )
            raise ManifestError(
                f"Arx path dependencies contain a cycle: {cycle}"
            )

        library_manifest = load_manifest(library_directory)
        library_layout = resolve_build_config(
            library_manifest, library_directory
        )
        module_name = library_layout.package
        if module_name != dependency_name:
            raise ManifestError(
                f"dependency {dependency_name!r} must match the library's "
                f"Arx package name {module_name!r} "
                f"(resolved from the library manifest)"
            )

        if resolved_library_directory in installed_paths:
            return

        installing_stack.append(resolved_library_directory)
        try:
            self._install_dependency_closure(
                directory,
                environment,
                library_directory,
                library_manifest,
                installing_stack,
                installed_paths,
            )
            pack_result = self.pack(library_directory)
            wheels = [
                artifact
                for artifact in pack_result.artifacts
                if artifact.suffix == ".whl"
            ]
            if not wheels:
                raise ManifestError(
                    f"packing {library_directory} produced no wheel artifact"
                )
            wheel = wheels[0]

            environment.install_packages(
                [str(wheel)],
                force_reinstall=True,
                no_deps=True,
            )
        finally:
            installing_stack.pop()
        installed_paths.add(resolved_library_directory)

    def _install_dependency_closure(
        self,
        directory: Path,
        environment: EnvironmentRuntime,
        dependency_directory: Path,
        dependency_manifest: Manifest,
        installing: list[Path],
        installed: set[Path],
    ) -> None:
        """
        title: Install dependencies of one Arx path dependency.
        parameters:
          directory:
            type: Path
          environment:
            type: EnvironmentRuntime
          dependency_directory:
            type: Path
          dependency_manifest:
            type: Manifest
          installing:
            type: list[Path]
          installed:
            type: set[Path]
        """
        registry_reqs, path_deps = _partition_dependencies(
            dependency_directory,
            dict(dependency_manifest.dependencies),
        )
        if registry_reqs:
            environment.install_packages(registry_reqs)

        for nested_name, nested_directory in path_deps:
            self._install_arx_path_dependency(
                directory,
                environment,
                nested_name,
                nested_directory,
                installing,
                installed,
            )


def _partition_dependencies(
    directory: Path,
    dependencies: dict[str, DependencySpec],
) -> tuple[list[str], list[tuple[str, Path]]]:
    registry_reqs: list[str] = []
    path_deps: list[tuple[str, Path]] = []
    for dependency_name, spec in sorted(dependencies.items()):
        if spec.path is not None:
            library_directory = (directory / spec.path).resolve()
            if _is_arx_project(library_directory):
                path_deps.append((dependency_name, library_directory))
                continue
        registry_reqs.append(_dependency_install_target(dependency_name, spec))
    return registry_reqs, path_deps


def _parse_bare_dependency_name(name: str) -> str:
    dependency_name, spec = DependencySpec.parse_requirement(name)
    if spec.kind != "registry" or spec.version_constraint is not None:
        raise ManifestError(
            "dependency name for --path or --git must be a bare package name"
        )
    return dependency_name


def _dependency_install_target(name: str, spec: DependencySpec) -> str:
    if spec.source is not None:
        if spec.version_constraint is not None:
            return f"{name}{spec.version_constraint}"
        return name
    if spec.path is not None:
        return spec.path
    if spec.git is not None:
        if spec.git.startswith("git+"):
            return spec.git
        return f"git+{spec.git}"
    raise ManifestError(f"dependency {name!r} has no installable target")


def _environment_install_requirements(
    manifest: Manifest,
    requirements: Sequence[str],
) -> list[str]:
    return [*effective_build_system_dependencies(manifest), *requirements]


def _compiler_command(
    environment: EnvironmentRuntime,
    source_path: str,
    artifact_rel: Path,
) -> list[str]:
    return [
        str(environment_executable(environment, _DEFAULT_ARX_COMPILER)),
        source_path,
        "--output-file",
        str(artifact_rel),
    ]


def _normalize_publish_value(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized:
        return normalized
    raise ManifestError(f"{name} cannot be empty")


def _publish_env_value(
    environ: Mapping[str, str],
    name: str,
) -> str | None:
    return _normalize_publish_value(name, environ.get(name))


def _build_publish_environment(
    environ: Mapping[str, str],
    repository_url: str | None,
    credential_store: PublishCredentialProvider,
) -> dict[str, str]:
    upload_environment = {
        key: value
        for key, value in environ.items()
        if not key.startswith(_PUBLISH_BACKEND_ENV_PREFIX)
    }
    repository_url_env = None
    if repository_url is None:
        repository_url_env = _publish_env_value(
            environ,
            _PUBLISH_ENV_REPOSITORY_URL,
        )
    token = _publish_env_value(environ, _PUBLISH_ENV_TOKEN)
    username = _publish_env_value(environ, _PUBLISH_ENV_USERNAME)
    password = _publish_env_value(environ, _PUBLISH_ENV_PASSWORD)

    if token is not None and (username is not None or password is not None):
        raise ManifestError(
            f"{_PUBLISH_ENV_TOKEN} cannot be combined with "
            f"{_PUBLISH_ENV_USERNAME} or {_PUBLISH_ENV_PASSWORD}"
        )

    if repository_url is None and repository_url_env is not None:
        upload_environment[_PUBLISH_BACKEND_REPOSITORY_URL] = (
            repository_url_env
        )

    if token is not None:
        upload_environment[_PUBLISH_BACKEND_USERNAME] = _PUBLISH_TOKEN_USERNAME
        upload_environment[_PUBLISH_BACKEND_PASSWORD] = token
        return upload_environment

    if username is not None:
        upload_environment[_PUBLISH_BACKEND_USERNAME] = username
    if password is not None:
        upload_environment[_PUBLISH_BACKEND_PASSWORD] = password
    if username is not None or password is not None:
        return upload_environment

    effective_repository_url = (
        repository_url or repository_url_env or PUBLISH_DEFAULT_REPOSITORY_URL
    )
    repository_name = _publish_repository_name(effective_repository_url)
    if repository_name is None:
        return upload_environment

    stored_token = credential_store.get_token(repository_name)
    if stored_token is None:
        return upload_environment

    upload_environment[_PUBLISH_BACKEND_USERNAME] = _PUBLISH_TOKEN_USERNAME
    upload_environment[_PUBLISH_BACKEND_PASSWORD] = stored_token
    return upload_environment


def _publish_repository_name(repository_url: str) -> str | None:
    normalized_url = repository_url.rstrip("/")
    if normalized_url == PUBLISH_DEFAULT_REPOSITORY_URL.rstrip("/"):
        return "pypi"
    if normalized_url == PUBLISH_TEST_REPOSITORY_URL.rstrip("/"):
        return "testpypi"
    return None


def _prepare_publish_workspace(
    directory: Path,
    manifest: Manifest,
    staging_dir: Path,
) -> None:
    layout = resolve_build_config(manifest, directory)
    package_name = layout.package
    package_root = staging_dir / "src" / package_name
    package_root.mkdir(parents=True, exist_ok=True)

    source_paths = _discover_arx_sources(directory, layout.package_root)
    if not source_paths:
        raise ManifestError(
            "no Arx source files found to publish (expected .x or .arx)"
        )

    source_root = layout.package_root.relative_to(directory)
    for relative_source in source_paths:
        source_path = directory / relative_source
        bundled_rel = _bundled_source_path(relative_source, source_root)
        target_path = package_root / bundled_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    manifest_path = directory / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")

    (package_root / MANIFEST_FILENAME).write_text(
        _render_packaged_manifest(manifest),
        encoding="utf-8",
    )
    (package_root / "__init__.py").write_text(
        _render_package_init(manifest),
        encoding="utf-8",
    )

    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "pyproject.toml").write_text(
        _render_publish_pyproject(manifest, package_name),
        encoding="utf-8",
    )
    (staging_dir / "README.md").write_text(
        _render_publish_readme(manifest),
        encoding="utf-8",
    )


def _bundled_source_path(relative_source: Path, source_root: Path) -> Path:
    """
    title: Drop the source root prefix so bundled files land at package root.
    parameters:
      relative_source:
        type: Path
      source_root:
        type: Path
    returns:
      type: Path
    """
    if source_root == Path("") or source_root == Path("."):
        return relative_source
    try:
        return relative_source.relative_to(source_root)
    except ValueError:
        return relative_source


def _discover_arx_sources(
    directory: Path,
    search_root: Path | None = None,
) -> list[Path]:
    root = search_root or directory
    sources: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _SOURCE_SUFFIXES:
            continue

        relative = path.relative_to(directory)
        if any(part in _EXCLUDED_SOURCE_DIRS for part in relative.parts):
            continue
        sources.append(relative)

    return sorted(sources)


def _is_arx_project(path: Path) -> bool:
    return path.is_dir() and (path / MANIFEST_FILENAME).is_file()


def _arx_module_name(project_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_")
    if not cleaned:
        raise ManifestError("project.name must contain letters or numbers")

    if cleaned[0].isdigit():
        cleaned = f"pkg_{cleaned}"
    return cleaned.lower()


def _render_package_init(manifest: Manifest) -> str:
    name = _toml_quote(manifest.project.name)
    version = _toml_quote(manifest.project.version)
    return (
        "\n".join(
            [
                '"""Generated Arx package metadata."""',
                "",
                f"PROJECT_NAME = {name}",
                f"PROJECT_VERSION = {version}",
                "",
                '__all__ = ["PROJECT_NAME", "PROJECT_VERSION"]',
            ]
        )
        + "\n"
    )


def _render_packaged_manifest(manifest: Manifest) -> str:
    packaged_manifest = Manifest(
        project=manifest.project,
        build=BuildConfig(
            src_dir=".",
            out_dir=manifest.build.out_dir,
            package=None,
            mode=manifest.build.mode,
        ),
        dependencies={
            name: _packaged_dependency_spec(spec)
            for name, spec in manifest.dependencies.items()
        },
        build_system=manifest.build_system,
    )
    return render_manifest(packaged_manifest)


def _packaged_dependency_spec(spec: DependencySpec) -> DependencySpec:
    if spec.path is not None:
        return DependencySpec.registry()
    return spec


def _render_publish_pyproject(
    manifest: Manifest,
    package_name: str,
) -> str:
    description = f"Published Arx package for project {manifest.project.name}."
    lines = [
        "[build-system]",
        'requires = ["hatchling>=1.25.0"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        f"name = {_toml_quote(manifest.project.name)}",
        f"version = {_toml_quote(manifest.project.version)}",
        f"description = {_toml_quote(description)}",
        'readme = "README.md"',
        'requires-python = ">=3.10"',
    ]
    dependencies = _publish_dependency_requirements(manifest)
    if dependencies:
        lines.extend(
            [
                "dependencies = [",
                *[
                    f"  {_toml_quote(dependency)},"
                    for dependency in dependencies
                ],
                "]",
            ]
        )
    lines.extend(
        [
            "",
            "[tool.hatch.build.targets.wheel]",
            f'packages = ["src/{package_name}"]',
            "include = [",
            f'  "src/{package_name}/**/*.x",',
            f'  "src/{package_name}/**/*.arx",',
            f'  "src/{package_name}/.arxproject.toml",',
            "]",
            "",
            "[tool.hatch.build.targets.sdist]",
            "include = [",
            f'  "src/{package_name}/**/*",',
            '  "README.md",',
            '  "pyproject.toml",',
            "]",
        ]
    )
    return "\n".join(lines) + "\n"


def _publish_dependency_requirements(manifest: Manifest) -> list[str]:
    requirements: list[str] = []
    for name, spec in sorted(manifest.dependencies.items()):
        requirements.append(_publish_dependency_requirement(name, spec))
    return requirements


def _publish_dependency_requirement(
    name: str,
    spec: DependencySpec,
) -> str:
    if spec.source is not None:
        if spec.version_constraint is not None:
            return f"{name}{spec.version_constraint}"
        return name
    if spec.path is not None:
        return name
    if spec.git is not None:
        git_url = spec.git
        if not git_url.startswith("git+"):
            git_url = f"git+{git_url}"
        return f"{name} @ {git_url}"
    raise ManifestError(f"dependency {name!r} has no publishable target")


def _render_publish_readme(manifest: Manifest) -> str:
    return (
        "\n".join(
            [
                f"# {manifest.project.name}",
                "",
                "This package was generated by arxpm publish.",
                "",
                "It includes:",
                "",
                "- .arxproject.toml",
                "- Arx source files (*.x, *.arx)",
            ]
        )
        + "\n"
    )


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _resolve_dependency_group_dependencies(
    manifest: Manifest,
    requested_groups: Sequence[str],
) -> dict[str, DependencySpec]:
    group_map = manifest.dependency_groups
    normalized_names = {
        _normalize_group_name(name): name for name in group_map
    }
    resolved: dict[str, DependencySpec] = {}
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(group_name: str) -> None:
        normalized_name = _normalize_group_name(group_name)
        if normalized_name not in normalized_names:
            raise ManifestError(f"unknown dependency group {group_name!r}")

        canonical_name = normalized_names[normalized_name]
        if canonical_name in visited:
            return
        if canonical_name in visiting:
            cycle = " -> ".join(visiting + [canonical_name])
            raise ManifestError(
                f"dependency group includes must not contain cycles: {cycle}"
            )

        visiting.append(canonical_name)
        for entry in group_map[canonical_name]:
            if isinstance(entry, str):
                dependency_name, spec = DependencySpec.parse_requirement(entry)
                _merge_dependency_spec(
                    resolved,
                    dependency_name,
                    spec,
                    label=f"dependency group {canonical_name!r}",
                )
                continue
            if isinstance(entry, DependencyGroupInclude):
                visit(entry.include_group)
                continue
            raise ManifestError(
                f"unsupported dependency group entry in {canonical_name!r}: "
                f"{entry!r}"
            )
        visiting.pop()
        visited.add(canonical_name)

    for group_name in requested_groups:
        visit(group_name)

    return resolved


def _merge_dependency_maps(
    base: dict[str, DependencySpec],
    extra: dict[str, DependencySpec],
    label: str,
) -> dict[str, DependencySpec]:
    merged = dict(base)
    for dependency_name, spec in extra.items():
        _merge_dependency_spec(merged, dependency_name, spec, label=label)
    return merged


def _merge_dependency_spec(
    target: dict[str, DependencySpec],
    dependency_name: str,
    spec: DependencySpec,
    label: str,
) -> None:
    existing = target.get(dependency_name)
    if existing is None:
        target[dependency_name] = spec
        return
    if existing != spec:
        raise ManifestError(
            f"{label} defines conflicting entries for {dependency_name!r}"
        )


def _normalize_group_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
