"""External process helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Protocol

from arxpm.errors import ExternalCommandError


@dataclass(slots=True, frozen=True)
class CommandResult:
    """External command result."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Callable interface for command runners."""

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        """Run a command and return its result."""


def run_command(
    command: Sequence[str],
    cwd: Path | None = None,
    check: bool = False,
) -> CommandResult:
    """Run a subprocess command."""
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    result = CommandResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode != 0:
        raise ExternalCommandError(
            result.command,
            result.returncode,
            result.stderr,
        )
    return result
