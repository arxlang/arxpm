"""Tests for pixi adapter behavior."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import tomllib

import pytest

from arxpm.errors import MissingPixiError
from arxpm.external import CommandResult
from arxpm.pixi import PixiService


class Recorder:
    """Record external command invocations."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None, bool]] = []

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        self.calls.append((list(command), cwd, check))
        return CommandResult(tuple(command), 0, "", "")


def test_detects_missing_pixi() -> None:
    service = PixiService(which=lambda _: None)

    assert service.is_available() is False
    with pytest.raises(MissingPixiError):
        service.ensure_available()


def test_ensure_manifest_creates_minimal_pixi_file(tmp_path: Path) -> None:
    service = PixiService(which=lambda _: "/usr/bin/pixi")
    path = service.ensure_manifest(tmp_path, "hello-arx", ("python", "clang"))

    assert path.exists()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["project"]["name"] == "hello-arx"
    assert "python" in data["dependencies"]
    assert "clang" in data["dependencies"]


def test_ensure_manifest_updates_missing_dependency(tmp_path: Path) -> None:
    pixi_file = tmp_path / "pixi.toml"
    pixi_file.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = "*"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = PixiService(which=lambda _: "/usr/bin/pixi")
    service.ensure_manifest(tmp_path, "demo", ("python", "clang"))

    data = tomllib.loads(pixi_file.read_text(encoding="utf-8"))
    assert "clang" in data["dependencies"]


def test_partial_sync_preserves_unrelated_sections(tmp_path: Path) -> None:
    pixi_file = tmp_path / "pixi.toml"
    pixi_file.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = "*"

[tasks]
build = "echo custom"

[feature.dev.dependencies]
pytest = "*"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = PixiService(which=lambda _: "/usr/bin/pixi")
    service.ensure_manifest(tmp_path, "demo", ("python", "clang"))

    content = pixi_file.read_text(encoding="utf-8")
    assert 'build = "echo custom"' in content
    assert "[feature.dev.dependencies]" in content
    assert 'clang = "*"' in content


def test_install_and_run_call_runner(tmp_path: Path) -> None:
    recorder = Recorder()
    service = PixiService(runner=recorder, which=lambda _: "/usr/bin/pixi")

    service.install(tmp_path)
    service.run(tmp_path, ["arx", "--version"])

    assert recorder.calls[0][0] == ["pixi", "install"]
    assert recorder.calls[1][0] == ["pixi", "run", "arx", "--version"]
