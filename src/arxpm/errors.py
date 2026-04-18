"""
title: Custom exceptions for arxpm.
"""

from __future__ import annotations

from collections.abc import Sequence


class ArxpmError(Exception):
    """
    title: Base exception for arxpm.
    """


class ManifestError(ArxpmError):
    """
    title: Manifest parsing or validation error.
    """


class MissingUvError(ArxpmError):
    """
    title: uv executable is missing.
    """


class MissingCompilerError(ArxpmError):
    """
    title: Arx compiler configuration is missing.
    """


class EnvironmentError(ArxpmError):
    """
    title: Environment runtime failure (invalid config, unreachable env, etc.).
    """


class ExternalCommandError(ArxpmError):
    """
    title: External command execution failed.
    attributes:
      command:
        type: tuple[str, Ellipsis]
      returncode:
        type: int
      stderr:
        type: str
    """

    command: tuple[str, ...]
    returncode: int
    stderr: str

    def __init__(
        self,
        command: Sequence[str],
        returncode: int,
        stderr: str,
    ) -> None:
        joined = " ".join(command)
        message = f"Command failed ({returncode}): {joined}"
        if stderr.strip():
            message = f"{message}\n{stderr.strip()}"
        super().__init__(message)
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
