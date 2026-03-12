"""
title: Tests for project workflow operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arxpm.errors import ManifestError
from arxpm.external import CommandResult
from arxpm.manifest import load_manifest
from arxpm.project import ProjectService

ManifestCall = tuple[Path, str, tuple[str, ...]]


class FakePixiService:
    """
    title: Pixi test double.
    attributes:
      ensure_manifest_calls:
        type: list[ManifestCall]
      install_calls:
        type: list[Path]
      run_calls:
        type: list[tuple[Path, list[str]]]
    """

    def __init__(self) -> None:
        self.ensure_manifest_calls: list[ManifestCall] = []
        self.install_calls: list[Path] = []
        self.run_calls: list[tuple[Path, list[str]]] = []

    def ensure_available(self) -> None:
        return None

    def ensure_manifest(
        self,
        directory: Path,
        project_name: str,
        required_dependencies: tuple[str, ...],
    ) -> Path:
        self.ensure_manifest_calls.append(
            (directory, project_name, required_dependencies)
        )
        return directory / "pixi.toml"

    def install(self, directory: Path) -> CommandResult:
        self.install_calls.append(directory)
        return CommandResult(("pixi", "install"), 0, "", "")

    def run(self, directory: Path, args: list[str]) -> CommandResult:
        self.run_calls.append((directory, args))

        if args[:3] == ["python", "-m", "build"] and "--outdir" in args:
            outdir_value = Path(args[args.index("--outdir") + 1])
            if outdir_value.is_absolute():
                outdir = outdir_value
            else:
                outdir = directory / outdir_value
            outdir.mkdir(parents=True, exist_ok=True)

            manifest = load_manifest(directory)
            normalized = manifest.project.name.replace("-", "_")
            version = manifest.project.version
            (outdir / f"{normalized}-{version}.tar.gz").write_text(
                "",
                encoding="utf-8",
            )
            (outdir / f"{normalized}-{version}-py3-none-any.whl").write_text(
                "",
                encoding="utf-8",
            )

        return CommandResult(("pixi", "run", *args), 0, "", "")


def test_init_and_add_dependency_forms(tmp_path: Path) -> None:
    service = ProjectService(pixi=FakePixiService())

    service.init(tmp_path, name="demo", create_pixi=False)
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


def test_build_and_run_delegate_to_pixi(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    build_result = service.build(tmp_path)
    run_result = service.run(tmp_path)

    assert build_result.artifact == tmp_path / "build" / "demo"
    assert pixi.run_calls[0][1][:3] == [
        "arx",
        "src/main.x",
        "--output-file",
    ]
    assert pixi.run_calls[-1][1] == ["build/demo"]
    assert run_result.build_result.artifact == tmp_path / "build" / "demo"


def test_install_calls_pixi_install(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    service.install(tmp_path)

    assert pixi.install_calls == [tmp_path]
    assert pixi.ensure_manifest_calls


def test_install_installs_manifest_dependencies_with_pip(
    tmp_path: Path,
) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    service.add_dependency(tmp_path, "http")
    service.add_dependency(tmp_path, "mylib", path=Path("../mylib"))
    service.add_dependency(
        tmp_path,
        "utils",
        git="https://example.com/utils.git",
    )

    service.install(tmp_path)

    commands = [call[1] for call in pixi.run_calls]
    assert commands == [
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "http",
        ],
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "../mylib",
        ],
        [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "git+https://example.com/utils.git",
        ],
    ]


def test_publish_builds_and_uploads_artifacts(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

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
    assert pixi.install_calls == [tmp_path]

    commands = [call[1] for call in pixi.run_calls]
    assert commands[0][:5] == [
        "python",
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
    ]
    assert commands[1][:3] == ["python", "-m", "build"]

    upload_command = commands[2]
    assert upload_command[:4] == ["python", "-m", "twine", "upload"]
    assert "--repository-url" in upload_command
    assert "--skip-existing" in upload_command


def test_pack_builds_artifacts_without_upload(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    pack_result = service.pack(tmp_path)

    assert [path.name for path in pack_result.artifacts] == [
        "demo-0.1.0-py3-none-any.whl",
        "demo-0.1.0.tar.gz",
    ]
    assert pack_result.upload_result is None
    assert len(pixi.run_calls) == 2


def test_publish_dry_run_skips_upload(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)
    service.init(tmp_path, name="demo", create_pixi=False)

    publish_result = service.publish(tmp_path, dry_run=True)

    assert publish_result.upload_result is None
    assert len(pixi.run_calls) == 2


def test_install_requires_arxproj_manifest(tmp_path: Path) -> None:
    pixi = FakePixiService()
    service = ProjectService(pixi=pixi)

    with pytest.raises(ManifestError):
        service.install(tmp_path)
