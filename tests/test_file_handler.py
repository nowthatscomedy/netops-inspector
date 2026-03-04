from __future__ import annotations

import pandas as pd
import pytest

import core.file_handler as file_handler_module
from core.file_handler import read_command_file, read_excel_file, save_results_to_excel
from core.i18n import set_locale


def test_read_command_file_from_txt(tmp_path) -> None:
    command_file = tmp_path / "commands.txt"
    command_file.write_text("show version\n\nshow running-config\n", encoding="utf-8")

    commands = read_command_file(str(command_file))
    assert commands == ["show version", "show running-config"]


def test_read_command_file_from_xlsx(tmp_path) -> None:
    command_file = tmp_path / "commands.xlsx"
    pd.DataFrame({0: ["show version", None, " show system "]}).to_excel(
        command_file, index=False, header=False
    )

    commands = read_command_file(str(command_file))
    assert commands == ["show version", "show system"]


def test_read_command_file_rejects_unknown_extension(tmp_path) -> None:
    command_file = tmp_path / "commands.csv"
    command_file.write_text("show version\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_command_file(str(command_file))


def test_read_excel_file_plain(tmp_path) -> None:
    excel_file = tmp_path / "devices.xlsx"
    expected = pd.DataFrame(
        [
            {"ip": "192.0.2.10", "vendor": "cisco", "os": "ios"},
            {"ip": "192.0.2.11", "vendor": "aruba", "os": "aruba_os"},
        ]
    )
    expected.to_excel(excel_file, index=False)

    loaded = read_excel_file(str(excel_file))
    pd.testing.assert_frame_equal(loaded, expected)


def test_read_excel_file_password_requires_msoffcrypto(monkeypatch, tmp_path) -> None:
    excel_file = tmp_path / "devices.xlsx"
    pd.DataFrame([{"ip": "192.0.2.10"}]).to_excel(excel_file, index=False)

    monkeypatch.setattr(file_handler_module, "msoffcrypto", None)
    with pytest.raises(ImportError):
        read_excel_file(str(excel_file), password="secret")


def test_save_results_to_excel_applies_alias_and_column_order(tmp_path) -> None:
    set_locale("en", "en")
    output_file = tmp_path / "result.xlsx"
    results = [
        {
            "ip": "192.0.2.10",
            "vendor": "cisco",
            "os": "ios",
            "status": "success",
            "inspection_results": {
                "host name": "edge-sw-1",
                "Hostname": "edge-sw-1-alt",
                "CPU Usage": "10%",
                "Version": "17.9.4a",
            },
        }
    ]

    save_results_to_excel(
        results,
        str(output_file),
        column_order=["Version", "Hostname", "CPU Usage"],
        column_aliases={
            "host name": "Hostname",
            "hostname": "Hostname",
            "cpu usage": "CPU Usage",
        },
    )

    df = pd.read_excel(output_file)
    assert {"Hostname", "Version", "CPU Usage"}.issubset(set(df.columns))
    assert "edge-sw-1" in str(df.loc[0, "Hostname"])
    assert "edge-sw-1-alt" in str(df.loc[0, "Hostname"])
    assert df.columns.get_loc("Version") < df.columns.get_loc("Hostname")
    assert df.columns.get_loc("Hostname") < df.columns.get_loc("CPU Usage")
