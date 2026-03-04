from __future__ import annotations

import pytest

from core.credential_utils import CredentialResolutionError, is_env_reference, resolve_credential


def test_is_env_reference() -> None:
    assert is_env_reference("env:NETOPS_PASSWORD") is True
    assert is_env_reference(" ENV:NETOPS_PASSWORD ") is True
    assert is_env_reference("plain-text") is False


def test_resolve_credential_plain_value() -> None:
    assert resolve_credential("secret", field_name="password") == "secret"


def test_resolve_credential_env_reference() -> None:
    resolved = resolve_credential(
        "env:NETOPS_PASSWORD",
        field_name="password",
        env={"NETOPS_PASSWORD": "secret-from-env"},
    )
    assert resolved == "secret-from-env"


def test_resolve_credential_env_reference_missing_raises() -> None:
    with pytest.raises(CredentialResolutionError):
        resolve_credential(
            "env:NETOPS_PASSWORD",
            field_name="password",
            env={},
        )
