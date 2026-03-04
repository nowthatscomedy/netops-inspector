# NetOps Inspector

Language: [English](README.md) | [한국어](docs/README.ko.md) | [日本語](docs/README.ja.md) | [Español](docs/README.es.md) | [Português (Brasil)](docs/README.pt-BR.md) | [简体中文](docs/README.zh-CN.md)

NetOps Inspector is a CLI tool for multi-vendor network device inspection and configuration backup.
It reads device inventories from Excel/CSV/JSON files, connects via SSH/Telnet, runs inspection commands, parses outputs, and writes result files (Excel/JSON/CSV).

## Key Features

- Multi-vendor architecture (`vendors/` modules)
- Inspection / Backup / Inspection+Backup execution modes
- Preflight mode (inventory + credential reference + TCP reachability check)
- Batch custom command execution from TXT or Excel files
- Inventory input validation (required fields, duplicate IP, vendor/OS compatibility)
- Retry and timeout controls for network I/O
- Real-time terminal dashboard during execution
- Session log files per device
- Result file generation (Excel/JSON/CSV) with configurable column alias/order
- User-defined parsing and command extensions via `custom_rules.yaml`
- i18n-ready UI/messages (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## Supported Vendors (Current Modules)

- `alcatel-lucent`
- `aruba`
- `axgate`
- `cisco`
- `dayou`
- `handreamnet`
- `juniper`
- `nexg`
- `piolink`
- `ruckus`
- `ubiquoss`

Supported OS values depend on each vendor module and `vendors/__init__.py` command maps.

## Requirements

- Python 3.10+
- Network reachability to target devices
- Dependencies in `requirements.txt`

Install:

```bash
pip install -r requirements.txt
```

## Quick Start

Run:

```bash
python main.py
```

Main menu:

1. Start inspection/backup
2. Run custom command file
3. Change settings
4. Show Netmiko `device_type` list
5. Run preflight check
6. Exit

## Inventory Input Schema

Supported inventory formats:

- Excel: `.xlsx`, `.xls`, `.xlsm`
- CSV: `.csv`
- JSON: `.json`
  - List form: `[{"ip":"...","vendor":"..."}]`
  - Wrapped form: `{"devices":[{"ip":"...","vendor":"..."}]}`

Example files:

- `examples/inventory/devices.csv`
- `examples/inventory/devices.json`
- `examples/inventory/devices_wrapped.json`

Required columns:

- `ip`
- `vendor`
- `os`
- `connection_type` (`ssh` or `telnet`)
- `port`
- `password`

Optional columns:

- `username`
- `enable_password`

Credential reference syntax (optional):

- `username`, `password`, `enable_password` may use `env:ENV_VAR_NAME`
- Example: `password: env:NETOPS_DEVICE_PASSWORD`
- If the referenced environment variable is missing/empty, the device is marked as failed safely

Example:

| ip | vendor | os | connection_type | port | username | password | enable_password |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 192.168.1.10 | cisco | ios | ssh | 22 | admin | ****** | ****** |
| 192.168.1.20 | ruckus | icx | ssh | 22 | super | ****** | |

## Settings (`settings.yaml`)

The file is auto-created in the app directory when missing.

Common keys:

- `console_log_level`: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`
- `max_retries`: max connect retries
- `timeout`: connect timeout (seconds)
- `max_workers`: parallel worker count
- `inspection_excludes`: per vendor/OS parse exclusion map
- `output_plugin`: `excel_results` | `json_results` | `csv_results`

Inspection output keys:

- `column_aliases`: normalize inspection column names
- `inspection_column_order_global`
- `inspection_column_order_by_profile`

i18n keys:

- `language`
- `fallback_language`
- `input_column_aliases`

Example:

```yaml
language: en
fallback_language: en
console_log_level: WARNING
max_retries: 3
timeout: 10
max_workers: 10

input_column_aliases:
  "ip address": ip
  "vendor name": vendor
  "connection type": connection_type

column_aliases:
  "host name": Hostname
  "cpu usage": CPU Usage

output_plugin: excel_results
```

## i18n

Language codes currently accepted:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

Translation files currently shipped:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

Unsupported language codes are normalized to `en`.
If a translation key is missing, messages fall back to `fallback_language`, then to English.

## Multilingual README

- Korean: `docs/README.ko.md`
- Japanese: `docs/README.ja.md`
- Spanish: `docs/README.es.md`
- Portuguese (Brazil): `docs/README.pt-BR.md`
- Simplified Chinese: `docs/README.zh-CN.md`

## Architecture Draft

- Plugin platform draft: `docs/plugin-platform-draft.md`

## Custom Rules (`custom_rules.yaml`)

You can extend commands/parsers without changing Python code.

Top-level sections:

- `inspection_commands`
- `backup_commands`
- `parsing_rules`
- `connection_overrides`
- `handler_overrides`

Template file:

- `custom_rules.example.yaml`

## Outputs

Generated paths (timestamped):

- Inspection results: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- Custom command results: `results/command_results_YYYYMMDD_HHMMSS.xlsx`
- Preflight results: `results/preflight_results_YYYYMMDD_HHMMSS.xlsx`
- JSON/CSV outputs when selected via `output_plugin`:
  - `results/*_YYYYMMDD_HHMMSS.json`
  - `results/*_YYYYMMDD_HHMMSS.csv`
- Backup files: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- Run logs: `logs/netops_inspector_YYYYMMDD_HHMMSS.log`
- Session logs: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## Testing

```bash
python -m pytest
```

## Build (Windows)

Use:

```bat
build.bat
```

## Security Notes

- Do not hardcode credentials in source files.
- Prefer environment variables or secured secret delivery for runtime credentials.
- Treat exported logs and result files as sensitive operational data.

## License

MIT License
