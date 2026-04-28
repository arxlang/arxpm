"""
title: Tests for publish credential storage.
"""

from __future__ import annotations

import pytest

import arxpm.credentials as credentials
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


def test_publish_credential_store_rejects_empty_token() -> None:
    with pytest.raises(ManifestError, match="publish token cannot be empty"):
        PublishCredentialStore().set_token_key("pypi-token.pypi", " ")


def test_publish_credential_store_rejects_invalid_repository_name() -> None:
    with pytest.raises(ManifestError, match="invalid publish repository"):
        PublishCredentialStore().get_token("bad repo")


def test_publish_credential_store_deletes_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.delete_password",
        lambda service, username: calls.append((service, username)),
    )

    repository = PublishCredentialStore().delete_token_key(
        "pypi-token.testpypi",
    )

    assert repository == "testpypi"
    assert calls == [("arxpm-publish", "testpypi")]


def test_publish_credential_store_reports_missing_deleted_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = credentials._keyring_module()

    def delete_password(_service: str, _username: str) -> None:
        raise keyring.errors.PasswordDeleteError("missing")

    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.delete_password",
        delete_password,
    )

    with pytest.raises(CredentialStoreError, match="No stored publish token"):
        PublishCredentialStore().delete_token_key("pypi-token.pypi")


def test_publish_credential_store_reports_delete_keyring_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = credentials._keyring_module()

    def delete_password(_service: str, _username: str) -> None:
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.delete_password",
        delete_password,
    )

    with pytest.raises(CredentialStoreError, match="Unable to remove"):
        PublishCredentialStore().delete_token_key("pypi-token.pypi")


def test_publish_credential_store_reports_set_keyring_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = credentials._keyring_module()

    def set_password(
        _service: str,
        _username: str,
        _password: str,
    ) -> None:
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.set_password",
        set_password,
    )

    with pytest.raises(CredentialStoreError, match="Unable to store"):
        PublishCredentialStore().set_token_key("pypi-token.pypi", "token")


def test_publish_credential_store_reports_get_keyring_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = credentials._keyring_module()

    def get_password(_service: str, _username: str) -> str:
        raise keyring.errors.KeyringError("locked")

    monkeypatch.setattr(
        "arxpm.credentials._keyring_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "arxpm.credentials._keyring.get_password",
        get_password,
    )

    with pytest.raises(CredentialStoreError, match="Unable to read"):
        PublishCredentialStore().get_token("pypi")


def test_keyring_available_handles_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = credentials._keyring_module()

    def get_keyring() -> object:
        raise keyring.errors.KeyringError("broken")

    monkeypatch.setattr(
        "arxpm.credentials._keyring.get_keyring",
        get_keyring,
    )

    assert credentials._keyring_available() is False


def test_keyring_available_handles_missing_keyring_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("arxpm.credentials._keyring", None)

    assert credentials._keyring_available() is False
