"""
title: End-to-end tests that compile and run the packaged examples.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from arxpm.pixi import PixiService
from arxpm.project import ProjectService

pytestmark = pytest.mark.integration

_TOOLCHAIN_AVAILABLE = (
    shutil.which("arx") is not None and shutil.which("pixi") is not None
)


@pytest.mark.skipif(
    not _TOOLCHAIN_AVAILABLE,
    reason="requires arx and pixi on PATH",
)
@pytest.mark.parametrize(
    "example_name, expected_substrings",
    [
        ("hello-arx", ("Hello, Arx!",)),
        ("multi-module", ("Hello, Arx!", "5")),
    ],
)
def test_example_runs_end_to_end(
    tmp_path: Path,
    example_name: str,
    expected_substrings: tuple[str, ...],
) -> None:
    source = Path(__file__).resolve().parents[1] / "examples" / example_name
    destination = tmp_path / example_name
    shutil.copytree(source, destination)

    service = ProjectService(pixi=PixiService())
    service.install(destination)
    result = service.run(destination)

    assert result.build_result.command_result.returncode == 0
    assert result.command_result.returncode == 0
    for expected in expected_substrings:
        assert expected in result.command_result.stdout


@pytest.mark.skipif(
    not _TOOLCHAIN_AVAILABLE,
    reason="requires arx and pixi on PATH",
)
def test_local_consumer_installs_and_runs_via_path_dep(tmp_path: Path) -> None:
    examples_root = Path(__file__).resolve().parents[1] / "examples"
    shutil.copytree(examples_root / "local_lib", tmp_path / "local_lib")
    consumer_dir = tmp_path / "local-consumer"
    shutil.copytree(examples_root / "local-consumer", consumer_dir)

    service = ProjectService(pixi=PixiService())
    service.install(consumer_dir)

    symlink = consumer_dir / "local_lib"
    assert symlink.is_symlink()
    assert (symlink / "stats.x").is_file()

    result = service.run(consumer_dir)

    assert result.build_result.command_result.returncode == 0
    assert result.command_result.returncode == 0
    assert "5" in result.command_result.stdout
