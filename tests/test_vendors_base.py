from __future__ import annotations

from typing import Any

import pytest

from vendors.base import GenericParamikoHandler, get_custom_handler, register_handler
from vendors.handreamnet import HandreamnetHnSSHHandler


def test_get_custom_handler_returns_registered_vendor_handler() -> None:
    device = {
        "ip": "192.0.2.10",
        "vendor": "handreamnet",
        "os": "hn",
        "connection_type": "ssh",
        "port": 22,
        "username": "admin",
        "password": "pw",
    }
    handler = get_custom_handler(device, timeout=7, session_log_file="session.log")
    assert isinstance(handler, HandreamnetHnSSHHandler)
    assert handler.timeout == 7


def test_get_custom_handler_uses_generic_os_fallback() -> None:
    @register_handler("acme-vendor", "*", "ssh")
    class AcmeGenericSshHandler(GenericParamikoHandler):
        pass

    device = {
        "ip": "192.0.2.20",
        "vendor": "acme-vendor",
        "os": "any-os",
        "connection_type": "ssh",
        "port": 22,
        "username": "admin",
        "password": "pw",
    }

    handler = get_custom_handler(device, timeout=11)
    assert isinstance(handler, AcmeGenericSshHandler)
    assert handler.timeout == 11


def test_get_custom_handler_returns_none_when_unregistered() -> None:
    device = {
        "ip": "192.0.2.30",
        "vendor": "unregistered-vendor",
        "os": "none",
        "connection_type": "ssh",
        "port": 22,
        "username": "admin",
        "password": "pw",
    }
    assert get_custom_handler(device) is None


def test_generic_paramiko_handler_rejects_non_ssh_connection() -> None:
    device: dict[str, Any] = {
        "ip": "192.0.2.40",
        "vendor": "acme",
        "os": "dummy",
        "connection_type": "telnet",
        "port": 23,
        "username": "admin",
        "password": "pw",
    }
    handler = GenericParamikoHandler(device)
    with pytest.raises(ValueError):
        handler.connect()
