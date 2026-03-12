"""
title: External process helpers.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arxpm.errors import ExternalCommandError


@dataclass(slots=True, frozen=True)
class CommandResult:
    """
    title: External command result.
    attributes:
      command:
        type: tuple[str, Ellipsis]
      returncode:
        type: int
      stdout:
        type: str
      stderr:
        type: str
    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """
    title: Callable interface for command runners.
    """

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> CommandResult:
        """
        title: Run a command and return its result.
        parameters:
          command:
            type: Sequence[str]
          cwd:
            type: Path | None
          check:
            type: bool
        returns:
          type: CommandResult
        """


def run_command(
    command: Sequence[str],
    cwd: Path | None = None,
    check: bool = False,
) -> CommandResult:
    """
    title: Run a subprocess command.
    parameters:
      command:
        type: Sequence[str]
      cwd:
        type: Path | None
      check:
        type: bool
    returns:
      type: CommandResult
    """
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

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if check and result.returncode != 0:
        raise ExternalCommandError(
            result.command,
            result.returncode,
            result.stderr,
        )
    return result
