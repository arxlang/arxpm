"""
title: Tests for module entry point.
"""

from __future__ import annotations

import runpy

import pytest

import arxpm.cli


def test_module_entry_point_invokes_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_app() -> None:
        calls.append("called")

    monkeypatch.setattr(arxpm.cli, "app", fake_app)

    runpy.run_module("arxpm.__main__", run_name="__main__")

    assert calls == ["called"]
