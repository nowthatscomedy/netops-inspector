from __future__ import annotations

import os
from collections.abc import Mapping


class CredentialResolutionError(ValueError):
    """Raised when a credential value cannot be resolved safely."""


_ENV_PREFIX = "env:"


def is_env_reference(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower().startswith(_ENV_PREFIX)


def resolve_credential(
    value: object,
    *,
    field_name: str,
    required: bool = True,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve plain or env-referenced credentials.

    Supported syntax:
    - plain text: `password123`
    - env reference: `env:NETOPS_PASSWORD`
    """
    source_env = env if env is not None else os.environ
    cleaned = str(value).strip() if value is not None else ""

    if is_env_reference(cleaned):
        env_name = cleaned[len(_ENV_PREFIX) :].strip()
        if not env_name:
            raise CredentialResolutionError(
                f"Invalid credential reference for '{field_name}': missing env variable name.",
            )
        resolved = source_env.get(env_name, "")
        if not str(resolved).strip():
            raise CredentialResolutionError(
                f"Credential env var for '{field_name}' is empty or missing: {env_name}",
            )
        return str(resolved)

    if required and not cleaned:
        raise CredentialResolutionError(f"Credential field is required: {field_name}")
    return cleaned
