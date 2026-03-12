"""
title: TOML parser compatibility helpers.
"""

from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]

__all__ = ["tomllib"]
