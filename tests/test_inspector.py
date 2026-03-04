from __future__ import annotations

import socket
import time
from typing import Any

import pytest

from core.inspector import NetworkInspector


@pytest.fixture()
def inspector(tmp_path, monkeypatch) -> NetworkInspector:
    monkeypatch.chdir(tmp_path)
    return NetworkInspector(
        output_excel="inspection_results.xlsx",
        run_timestamp="20260101_010101",
        max_retries=2,
        timeout=1,
        max_workers=2,
        column_aliases={"host name": "Hostname", "hostname": "Hostname"},
    )


def test_canonicalize_result_columns_merges_alias(inspector: NetworkInspector) -> None:
    merged = inspector._canonicalize_result_columns(
        {
            "host name": "edge-sw-1",
            "Hostname": "edge-sw-1-alt",
            "CPU Usage": "10%",
        }
    )
    assert merged["Hostname"] == "edge-sw-1, edge-sw-1-alt"
    assert merged["CPU Usage"] == "10%"


def test_get_output_columns_for_known_command(inspector: NetworkInspector) -> None:
    columns = inspector._get_output_columns_for_command("cisco", "ios", "show env all")
    assert columns == ["Fan Status", "System Temperature"]


def test_get_available_inspection_columns_respects_excludes(
    inspector: NetworkInspector,
) -> None:
    inspector.inspection_excludes = {
        "cisco": {"ios": ["show env all::Fan Status", "show version | include uptime"]}
    }
    devices = [{"vendor": "cisco", "os": "ios"}]

    columns = inspector.get_available_inspection_columns(devices)
    assert "Hostname" in columns
    assert "System Temperature" in columns
    assert "CPU Usage" in columns
    assert "Memory Usage" in columns
    assert "Fan Status" not in columns
    assert "Uptime" not in columns


def test_parse_command_output_custom_parser_and_parse_id_exclude(
    inspector: NetworkInspector,
) -> None:
    parsed_hostname = inspector._parse_command_output(
        "cisco",
        "ios",
        "show running-config",
        'hostname "dist-sw-1"',
    )
    assert parsed_hostname["Hostname"].strip('"') == "dist-sw-1"

    inspector.inspection_excludes = {"cisco": {"ios": ["show env all::Fan Status"]}}
    parsed_env = inspector._parse_command_output(
        "cisco",
        "ios",
        "show env all",
        "FAN 1 is OK\nTEMPERATURE is GREEN\n",
    )
    assert "Fan Status" not in parsed_env
    assert parsed_env["System Temperature"] == "GREEN"


def test_connect_to_device_returns_error_when_tcp_test_fails(
    inspector: NetworkInspector, sample_device: dict[str, Any], monkeypatch
) -> None:
    monkeypatch.setattr(inspector, "_test_tcping", lambda ip, port: False)
    _, result = inspector._connect_to_device(
        dict(sample_device),
        inspection_mode=True,
        backup_mode=False,
    )
    assert "error" in result
    assert "TCP" in str(result["error"])


def test_inspect_device_marks_status_error_on_connection_failure(
    inspector: NetworkInspector, sample_device: dict[str, Any], monkeypatch
) -> None:
    def fake_connect(device: dict[str, Any], *args, **kwargs):
        return device, {"error": "auth failed"}

    monkeypatch.setattr(inspector, "_connect_to_device", fake_connect)
    result = inspector._inspect_device(dict(sample_device))

    assert result["status"] == "error"
    assert result["error_message"] == "auth failed"
    assert result["_elapsed_seconds"] >= 0


def test_backup_device_propagates_backup_error(
    inspector: NetworkInspector, sample_device: dict[str, Any], monkeypatch
) -> None:
    def fake_connect(device: dict[str, Any], *args, **kwargs):
        return device, {"backup_error": "disk full"}

    monkeypatch.setattr(inspector, "_connect_to_device", fake_connect)
    result = inspector._backup_device(dict(sample_device))

    assert result["status"] == "error"
    assert result["error_message"] == "disk full"


def test_inspect_devices_sorts_results_by_input_order(
    inspector: NetworkInspector, monkeypatch
) -> None:
    devices = [
        {
            "ip": "192.0.2.11",
            "vendor": "cisco",
            "os": "ios",
            "connection_type": "ssh",
            "port": 22,
            "username": "u",
            "password": "p",
        },
        {
            "ip": "192.0.2.10",
            "vendor": "cisco",
            "os": "ios",
            "connection_type": "ssh",
            "port": 22,
            "username": "u",
            "password": "p",
        },
    ]
    inspector.load_devices(devices)

    def fake_inspect(device: dict[str, Any]) -> dict[str, Any]:
        if device["ip"] == "192.0.2.11":
            time.sleep(0.05)
        return {
            "ip": device["ip"],
            "vendor": device["vendor"],
            "os": device["os"],
            "status": "success",
            "error_message": "",
            "inspection_results": {},
            "_elapsed_seconds": 0.01,
        }

    monkeypatch.setattr(inspector, "_inspect_device", fake_inspect)
    monkeypatch.setattr(inspector, "_print_cli_status", lambda message: None)
    monkeypatch.setattr(inspector, "_emit_status_event", lambda *args, **kwargs: None)

    inspector.inspect_devices()
    assert [row["ip"] for row in inspector.results] == ["192.0.2.11", "192.0.2.10"]


def test_inspect_devices_handles_worker_exception_without_crashing(
    inspector: NetworkInspector, monkeypatch
) -> None:
    devices = [
        {
            "ip": "192.0.2.10",
            "vendor": "cisco",
            "os": "ios",
            "connection_type": "ssh",
            "port": 22,
            "username": "u",
            "password": "p",
        }
    ]
    inspector.load_devices(devices)

    def boom(device: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(inspector, "_inspect_device", boom)
    monkeypatch.setattr(inspector, "_print_cli_status", lambda message: None)
    monkeypatch.setattr(inspector, "_emit_status_event", lambda *args, **kwargs: None)

    inspector.inspect_devices()
    assert len(inspector.results) == 1
    assert inspector.results[0]["status"] == "error"
    assert "boom" in inspector.results[0]["error_message"]


def test_test_tcping_supports_ipv6(inspector: NetworkInspector, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeSocket:
        def __init__(self, family: int, socktype: int, proto: int) -> None:
            captured["family"] = family
            captured["socktype"] = socktype
            captured["proto"] = proto

        def __enter__(self) -> "_FakeSocket":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def settimeout(self, timeout: int) -> None:
            captured["timeout"] = timeout

        def connect_ex(self, sockaddr: object) -> int:
            captured["sockaddr"] = sockaddr
            return 0

    monkeypatch.setattr(
        "core.inspector.socket.getaddrinfo",
        lambda ip, port, family, socktype: [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                0,
                "",
                ("2001:db8::1", port, 0, 0),
            )
        ],
    )
    monkeypatch.setattr(
        "core.inspector.socket.socket",
        lambda family, socktype, proto: _FakeSocket(family, socktype, proto),
    )

    assert inspector._test_tcping("2001:db8::1", 22, timeout=3) is True
    assert captured["family"] == socket.AF_INET6


def test_connect_to_device_returns_error_for_missing_password_env(
    inspector: NetworkInspector, sample_device: dict[str, Any], monkeypatch
) -> None:
    device = dict(sample_device)
    device["password"] = "env:NETOPS_MISSING_PASSWORD"
    monkeypatch.setattr(inspector, "_test_tcping", lambda ip, port: True)
    _, result = inspector._connect_to_device(
        device,
        inspection_mode=False,
        backup_mode=False,
    )
    assert "error" in result
    assert "NETOPS_MISSING_PASSWORD" in str(result["error"])
