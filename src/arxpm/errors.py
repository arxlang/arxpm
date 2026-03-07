"""Custom exceptions for arxpm."""

from __future__ import annotations

from collections.abc import Sequence


class ArxpmError(Exception):
    """Base exception for arxpm."""


class ManifestError(ArxpmError):
    """Manifest parsing or validation error."""


class MissingPixiError(ArxpmError):
    """Pixi executable is missing."""


class MissingCompilerError(ArxpmError):
    """Arx compiler configuration is missing."""


class ExternalCommandError(ArxpmError):
    """External command execution failed."""

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
