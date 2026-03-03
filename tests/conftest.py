from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture()
def sample_device() -> dict[str, Any]:
    return {
        "ip": "192.0.2.10",
        "vendor": "cisco",
        "os": "ios",
        "connection_type": "ssh",
        "port": 22,
        "username": "admin",
        "password": "password",
        "enable_password": "enable-password",
    }
