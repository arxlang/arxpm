"""
title: Tests for publish credential storage.
"""

from __future__ import annotations

import pytest

from arxpm.credentials import PublishCredentialStore
from arxpm.errors import CredentialStoreError, ManifestError


def test_publish_credential_store_writes_token_to_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.set_password",
        lambda service, username, password: calls.append(
            (service, username, password)
        ),
    )

    repository = PublishCredentialStore().set_token_key(
        "pypi-token.PyPI",
        " pypi-token ",
    )

    assert repository == "pypi"
    assert calls == [("arxpm-publish", "pypi", "pypi-token")]


def test_publish_credential_store_reads_token_from_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.get_password",
        lambda service, username: f"{service}:{username}:token",
    )

    token = PublishCredentialStore().get_token("TestPyPI")

    assert token == "arxpm-publish:testpypi:token"


def test_publish_credential_store_skips_unavailable_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: False,
    )

    token = PublishCredentialStore().get_token("pypi")

    assert token is None


def test_publish_credential_store_rejects_unsupported_key() -> None:
    with pytest.raises(ManifestError, match="expected pypi-token"):
        PublishCredentialStore().set_token_key("repositories.pypi", "token")


def test_publish_credential_store_requires_keyring_for_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: False,
    )

    with pytest.raises(CredentialStoreError, match="No supported system"):
        PublishCredentialStore().set_token_key("pypi-token.pypi", "token")


def test_publish_credential_store_reports_missing_keyring_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.credentials._keyring", None)

    with pytest.raises(
        CredentialStoreError,
        match="keyring package is not available",
    ):
        PublishCredentialStore().ensure_available()
