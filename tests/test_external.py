"""
title: Tests for external command helpers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from arxpm.errors import ExternalCommandError
from arxpm.external import run_command


def test_run_command_forwards_stdout_and_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run_command(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "print('hello from stdout'); "
                "print('hello from stderr', file=sys.stderr)"
            ),
        ],
        cwd=tmp_path,
    )

    captured = capsys.readouterr()

    assert result.returncode == 0
    assert result.stdout == "hello from stdout\n"
    assert result.stderr == "hello from stderr\n"
    assert captured.out == "hello from stdout\n"
    assert captured.err == "hello from stderr\n"


def test_run_command_accepts_custom_environment(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["ARXPM_TEST_ENV"] = "custom-value"

    result = run_command(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ['ARXPM_TEST_ENV'])",
        ],
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0
    assert result.stdout == "custom-value\n"


def test_run_command_check_raises_external_error() -> None:
    with pytest.raises(ExternalCommandError) as exc_info:
        run_command(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('fatal', file=sys.stderr); "
                    "raise SystemExit(3)"
                ),
            ],
            check=True,
        )

    error = exc_info.value
    assert error.returncode == 3
    assert "fatal" in error.stderr
