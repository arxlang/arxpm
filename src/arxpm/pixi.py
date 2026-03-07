"""Pixi integration layer."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import json
from pathlib import Path
import shutil
import tomllib
from typing import Any

from arxpm.errors import ManifestError, MissingPixiError
from arxpm.external import CommandResult, CommandRunner, run_command

PIXI_FILENAME = "pixi.toml"
DEFAULT_CHANNELS = ("conda-forge",)
DEFAULT_PLATFORMS = ("linux-64", "osx-64", "win-64")
BASE_DEPENDENCIES = ("python", "clang")


class PixiService:
    """Facade around pixi CLI operations."""

    def __init__(
        self,
        runner: CommandRunner = run_command,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._runner = runner
        self._which = which

    @staticmethod
    def pixi_path(directory: Path) -> Path:
        """Return pixi.toml path for a project directory."""
        return directory / PIXI_FILENAME

    def is_available(self) -> bool:
        """Check if pixi is available on PATH."""
        return self._which("pixi") is not None

    def ensure_available(self) -> None:
        """Raise when pixi is not available."""
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
        """Create or update a minimal pixi.toml."""
        path = self.pixi_path(directory)
        data = _load_pixi_data(path) if path.exists() else {}

        project = _normalize_project(data.get("project"), project_name)
        dependencies = _normalize_dependencies(data.get("dependencies"))

        changed = not path.exists()
        for dependency in required_dependencies:
            key = dependency.strip()
            if not key:
                continue
            if key not in dependencies:
                dependencies[key] = "*"
                changed = True

        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            text = render_pixi_manifest(project, dependencies)
            path.write_text(text, encoding="utf-8")

        return path

    def install(self, directory: Path) -> CommandResult:
        """Run pixi install in a project directory."""
        return self._runner(["pixi", "install"], cwd=directory, check=True)

    def run(self, directory: Path, args: Iterable[str]) -> CommandResult:
        """Run a command via pixi run."""
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
    """Render a minimal pixi.toml."""
    lines = [
        "[project]",
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


def _load_pixi_data(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("pixi.toml root must be a table")
    return data


def _normalize_project(raw: Any, project_name: str) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ManifestError("pixi [project] must be a table")

    name = raw.get("name", project_name)
    version = raw.get("version", "0.1.0")
    channels = raw.get("channels", list(DEFAULT_CHANNELS))
    platforms = raw.get("platforms", list(DEFAULT_PLATFORMS))

    if not isinstance(name, str) or not name.strip():
        raise ManifestError("pixi project.name must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ManifestError("pixi project.version must be a non-empty string")

    return {
        "name": name,
        "version": version,
        "channels": _normalize_array(channels, "project.channels"),
        "platforms": _normalize_array(platforms, "project.platforms"),
    }


def _normalize_dependencies(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ManifestError("pixi [dependencies] must be a table")

    parsed: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ManifestError("pixi dependency name must be non-empty")
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(
                f"pixi dependency {key!r} must be a non-empty string"
            )
        parsed[key] = value
    return parsed


def _normalize_array(raw: Any, label: str) -> list[str]:
    if not isinstance(raw, list):
        raise ManifestError(f"pixi {label} must be an array of strings")

    parsed: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ManifestError(
                f"pixi {label} entries must be non-empty strings"
            )
        parsed.append(item)
    return parsed


def _array(values: Any) -> str:
    text = ", ".join(_quote(str(value)) for value in values)
    return f"[{text}]"


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)
