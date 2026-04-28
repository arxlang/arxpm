"""
title: Publish credential storage helpers.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, cast

from arxpm.errors import CredentialStoreError, ManifestError

_imported_keyring: Any | None
try:
    import keyring as _imported_keyring
except ImportError:
    _imported_keyring = None

_keyring: Any | None = _imported_keyring

_PUBLISH_TOKEN_KEY_PREFIX = "pypi-token."
_PUBLISH_KEYRING_SERVICE = "arxpm-publish"
_REPOSITORY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class PublishCredentialProvider(Protocol):
    """
    title: Interface for publish credential providers.
    """

    def get_token(self, repository: str) -> str | None:
        """
        title: Return a stored publish token for a repository.
        parameters:
          repository:
            type: str
        returns:
          type: str | None
        """


class PublishCredentialStore:
    """
    title: Keyring-backed publish credential store.
    """

    def ensure_available(self) -> None:
        """
        title: Verify that a supported system keyring is available.
        """
        if _keyring_available():
            return
        raise CredentialStoreError(
            "No supported system keyring is available. Use "
            "ARXPM_PUBLISH_TOKEN for this publish, or configure a "
            "supported keyring backend."
        )

    def set_token_key(self, key: str, token: str) -> str:
        """
        title: Store a publish token from an arxpm config key.
        parameters:
          key:
            type: str
          token:
            type: str
        returns:
          type: str
        """
        repository = _repository_from_token_key(key)
        normalized_token = token.strip()
        if not normalized_token:
            raise ManifestError("publish token cannot be empty")

        keyring = _keyring_module()
        self.ensure_available()
        try:
            keyring.set_password(
                _PUBLISH_KEYRING_SERVICE,
                repository,
                normalized_token,
            )
        except keyring.errors.KeyringError as exc:
            raise CredentialStoreError(
                "Unable to store publish token in the system keyring. "
                "Use ARXPM_PUBLISH_TOKEN for this publish, or configure "
                "a supported keyring backend."
            ) from exc
        return repository

    def delete_token_key(self, key: str) -> str:
        """
        title: Remove a stored publish token from an arxpm config key.
        parameters:
          key:
            type: str
        returns:
          type: str
        """
        repository = _repository_from_token_key(key)
        keyring = _keyring_module()
        self.ensure_available()
        try:
            keyring.delete_password(_PUBLISH_KEYRING_SERVICE, repository)
        except keyring.errors.PasswordDeleteError as exc:
            raise CredentialStoreError(
                f"No stored publish token found for repository {repository!r}."
            ) from exc
        except keyring.errors.KeyringError as exc:
            raise CredentialStoreError(
                "Unable to remove publish token from the system keyring."
            ) from exc
        return repository

    def get_token(self, repository: str) -> str | None:
        """
        title: Return a stored publish token from the system keyring.
        parameters:
          repository:
            type: str
        returns:
          type: str | None
        """
        normalized_repository = _normalize_repository_name(repository)
        if not _keyring_available():
            return None
        keyring = _keyring_module()
        try:
            token = keyring.get_password(
                _PUBLISH_KEYRING_SERVICE,
                normalized_repository,
            )
        except keyring.errors.KeyringError as exc:
            raise CredentialStoreError(
                "Unable to read publish token from the system keyring. "
                "Use ARXPM_PUBLISH_TOKEN for this publish, or unlock "
                "your keyring."
            ) from exc
        return cast(str | None, token)


def _repository_from_token_key(key: str) -> str:
    normalized_key = key.strip().casefold()
    if not normalized_key.startswith(_PUBLISH_TOKEN_KEY_PREFIX):
        raise ManifestError(
            f"unsupported config key {key!r}; expected pypi-token.<repository>"
        )

    repository = normalized_key[len(_PUBLISH_TOKEN_KEY_PREFIX) :]
    return _normalize_repository_name(repository)


def _normalize_repository_name(repository: str) -> str:
    normalized = repository.strip().casefold()
    if _REPOSITORY_NAME_RE.fullmatch(normalized):
        return normalized
    raise ManifestError(f"invalid publish repository name: {repository!r}")


def _keyring_available() -> bool:
    try:
        keyring = _keyring_module()
    except CredentialStoreError:
        return False
    try:
        backend = keyring.get_keyring()
    except keyring.errors.KeyringError:
        return False
    return getattr(backend, "priority", 0) > 0


def _keyring_module() -> Any:
    if _keyring is not None:
        return _keyring
    raise CredentialStoreError(
        "The keyring package is not available. Use ARXPM_PUBLISH_TOKEN "
        "for this publish, or install arxpm with keyring support."
    )
