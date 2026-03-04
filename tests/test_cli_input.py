from __future__ import annotations

import core.cli_input as cli_input


class _FakePrompt:
    def __init__(self, value: str | None) -> None:
        self._value = value

    def execute(self) -> str | None:
        return self._value


def test_get_filepath_from_cli_accepts_csv(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "ip,vendor,os,connection_type,port,password\n"
        "192.0.2.10,cisco,ios,ssh,22,pw\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(str(csv_path)),
    )
    result = cli_input.get_filepath_from_cli()
    assert result == str(csv_path)


def test_get_filepath_from_cli_accepts_json(monkeypatch, tmp_path) -> None:
    json_path = tmp_path / "devices.json"
    json_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(str(json_path)),
    )
    result = cli_input.get_filepath_from_cli()
    assert result == str(json_path)


def test_get_filepath_from_cli_rejects_unsupported_extension(monkeypatch, tmp_path) -> None:
    txt_path = tmp_path / "devices.txt"
    txt_path.write_text("nope", encoding="utf-8")
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(str(txt_path)),
    )
    result = cli_input.get_filepath_from_cli()
    assert result is None


def test_get_filepath_from_cli_returns_none_for_empty_value(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(None),
    )
    assert cli_input.get_filepath_from_cli() is None


def test_validate_extension_handles_inventory_extensions() -> None:
    assert cli_input._validate_extension("devices.xlsx", cli_input.INVENTORY_EXTENSIONS)
    assert cli_input._validate_extension("devices.csv", cli_input.INVENTORY_EXTENSIONS)
    assert cli_input._validate_extension("devices.json", cli_input.INVENTORY_EXTENSIONS)
    assert not cli_input._validate_extension("devices.txt", cli_input.INVENTORY_EXTENSIONS)
    assert not cli_input._validate_extension("", cli_input.INVENTORY_EXTENSIONS)


def test_get_command_filepath_from_cli_rejects_csv(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "commands.csv"
    csv_path.write_text("show version", encoding="utf-8")
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(str(csv_path)),
    )
    result = cli_input.get_command_filepath_from_cli()
    assert result is None


def test_get_command_filepath_from_cli_accepts_txt(monkeypatch, tmp_path) -> None:
    txt_path = tmp_path / "commands.txt"
    txt_path.write_text("show version", encoding="utf-8")
    monkeypatch.setattr(
        cli_input.inquirer,
        "filepath",
        lambda **kwargs: _FakePrompt(str(txt_path)),
    )
    result = cli_input.get_command_filepath_from_cli()
    assert result == str(txt_path)
