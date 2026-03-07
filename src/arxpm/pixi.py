"""
title: Pixi integration layer.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from arxpm.errors import ManifestError, MissingPixiError
from arxpm.external import CommandResult, CommandRunner, run_command

PIXI_FILENAME = "pixi.toml"
DEFAULT_CHANNELS = ("conda-forge",)
DEFAULT_PLATFORMS = ("linux-64", "osx-64", "win-64")
BASE_DEPENDENCIES = ("python", "clang")
_SIMPLE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class PixiService:
    """
    title: Facade around pixi CLI operations.
    attributes:
      _runner:
        type: CommandRunner
      _which:
        type: Callable[[str], str | None]
    """

    _runner: CommandRunner
    _which: Callable[[str], str | None]

    def __init__(
        self,
        runner: CommandRunner = run_command,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._runner = runner
        self._which = which

    @staticmethod
    def pixi_path(directory: Path) -> Path:
        """
        title: Return pixi.toml path for a project directory.
        parameters:
          directory:
            type: Path
        returns:
          type: Path
        """
        return directory / PIXI_FILENAME

    def is_available(self) -> bool:
        """
        title: Check if pixi is available on PATH.
        returns:
          type: bool
        """
        return self._which("pixi") is not None

    def ensure_available(self) -> None:
        """
        title: Raise when pixi is not available.
        """
        if not self.is_available():
            raise MissingPixiError(
                "pixi is required but was not found on PATH"
            )

    def ensure_manifest(
        self,
        directory: Path,
        project_name: str,
        required_dependencies: Iterable[str] = BASE_DEPENDENCIES,
    ) -> Path:
        """
        title: Create or partially sync pixi.toml for arxpm-managed fields.
        parameters:
          directory:
            type: Path
          project_name:
            type: str
          required_dependencies:
            type: Iterable[str]
        returns:
          type: Path
        """
        path = self.pixi_path(directory)
        required = _normalize_required(required_dependencies)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            text = render_minimal_manifest(project_name, required)
            path.write_text(text, encoding="utf-8")
            return path

        original = path.read_text(encoding="utf-8")
        data = _load_pixi_data(path)
        existing = _declared_dependency_names(data)
        missing = [name for name in required if name not in existing]

        updated = original
        if missing:
            updated = _insert_dependency_entries(updated, missing)
        if not _has_arxpm_section(data):
            updated = _append_arxpm_section(updated, required)

        if updated != original:
            _validate_toml_text(updated, path)
            path.write_text(updated, encoding="utf-8")
        return path

    def declared_dependencies(self, directory: Path) -> set[str]:
        """
        title: Return declared pixi dependency names.
        parameters:
          directory:
            type: Path
        returns:
          type: set[str]
        """
        path = self.pixi_path(directory)
        if not path.exists():
            return set()
        data = _load_pixi_data(path)
        return _declared_dependency_names(data)

    def install(self, directory: Path) -> CommandResult:
        """
        title: Run pixi install in a project directory.
        parameters:
          directory:
            type: Path
        returns:
          type: CommandResult
        """
        return self._runner(["pixi", "install"], cwd=directory, check=True)

    def run(self, directory: Path, args: Iterable[str]) -> CommandResult:
        """
        title: Run a command via pixi run.
        parameters:
          directory:
            type: Path
          args:
            type: Iterable[str]
        returns:
          type: CommandResult
        """
        command = [part for part in args if part]
        if not command:
            raise ManifestError("pixi run command cannot be empty")
        return self._runner(
            ["pixi", "run", *command],
            cwd=directory,
            check=True,
        )


def render_pixi_manifest(
    project: Mapping[str, Any],
    dependencies: Mapping[str, str],
) -> str:
    """
    title: Render a minimal pixi.toml.
    parameters:
      project:
        type: Mapping[str, Any]
      dependencies:
        type: Mapping[str, str]
    returns:
      type: str
    """
    lines = [
        "[workspace]",
        f"name = {_quote(str(project['name']))}",
        f"version = {_quote(str(project['version']))}",
        f"channels = {_array(project['channels'])}",
        f"platforms = {_array(project['platforms'])}",
        "",
        "[dependencies]",
    ]
    for name, value in sorted(dependencies.items()):
        lines.append(f"{_quote(name)} = {_quote(value)}")
    return "\n".join(lines) + "\n"


def render_minimal_manifest(
    project_name: str,
    required_dependencies: Iterable[str] = BASE_DEPENDENCIES,
) -> str:
    """
    title: Render a minimal pixi.toml for arxpm bootstrap.
    parameters:
      project_name:
        type: str
      required_dependencies:
        type: Iterable[str]
    returns:
      type: str
    """
    required = _normalize_required(required_dependencies)
    project = {
        "name": project_name,
        "version": "0.1.0",
        "channels": list(DEFAULT_CHANNELS),
        "platforms": list(DEFAULT_PLATFORMS),
    }
    dependencies = {name: "*" for name in required}
    text = render_pixi_manifest(project, dependencies)
    return _append_arxpm_section(text, required)


def _load_pixi_data(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("pixi.toml root must be a table")
    return data


def _validate_toml_text(text: str, path: Path) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc


def _declared_dependency_names(data: Mapping[str, Any]) -> set[str]:
    dependencies_raw = data.get("dependencies")
    if dependencies_raw is None:
        return set()
    if not isinstance(dependencies_raw, Mapping):
        raise ManifestError("pixi [dependencies] must be a table")

    names: set[str] = set()
    for key in dependencies_raw:
        if not isinstance(key, str) or not key.strip():
            raise ManifestError("pixi dependency name must be non-empty")
        names.add(key)
    return names


def _normalize_required(required: Iterable[str]) -> tuple[str, ...]:
    cleaned = {value.strip() for value in required if value.strip()}
    return tuple(sorted(cleaned))


def _has_arxpm_section(data: Mapping[str, Any]) -> bool:
    tool = data.get("tool")
    if not isinstance(tool, Mapping):
        return False
    return isinstance(tool.get("arxpm"), Mapping)


def _append_arxpm_section(text: str, required: Iterable[str]) -> str:
    entries = ", ".join(_quote(dep) for dep in required)
    block = [
        "[tool.arxpm]",
        f"managed_dependencies = [{entries}]",
    ]
    return _append_table_block(text, block)


def _insert_dependency_entries(
    text: str,
    dependency_names: Iterable[str],
) -> str:
    lines = text.splitlines()
    table = _find_table_bounds(lines, "dependencies")
    entries = [f'{_format_key(name)} = "*"' for name in dependency_names]

    if table is None:
        block = ["[dependencies]", *entries]
        return _append_table_block(text, block)

    _, end = table
    updated = lines[:end] + entries + lines[end:]
    return "\n".join(updated) + "\n"


def _append_table_block(text: str, block: list[str]) -> str:
    normalized = text
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    if normalized and not normalized.endswith("\n\n"):
        normalized += "\n"
    return normalized + "\n".join(block) + "\n"


def _find_table_bounds(
    lines: list[str],
    table_name: str,
) -> tuple[int, int] | None:
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        header = _table_header_name(line)
        if header is None:
            continue
        if start is None:
            if header == table_name:
                start = index
            continue
        end = index
        break
    if start is None:
        return None
    return (start, end)


def _table_header_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    if stripped.startswith("[["):
        return None
    return stripped[1:-1].strip()


def _format_key(key: str) -> str:
    if _SIMPLE_KEY_PATTERN.fullmatch(key):
        return key
    return _quote(key)


def _array(values: Any) -> str:
    text = ", ".join(_quote(str(value)) for value in values)
    return f"[{text}]"


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)
