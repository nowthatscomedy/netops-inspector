# Plugin Platform Draft

This draft introduces a plugin-oriented execution model without breaking existing workflows.

## Goals

- Keep current menu UX and default behavior intact.
- Decouple execution pipeline into three plugin stages:
  - inventory
  - task
  - output
- Allow new inventory/output backends without rewriting `main.py`.

## New Components

- `core/plugin_platform/contracts.py`
  - Shared dataclasses and plugin interfaces.
- `core/plugin_platform/registry.py`
  - Runtime plugin registry.
- `core/plugin_platform/runtime.py`
  - Thin dispatcher that executes plugins.
- `core/plugin_platform/legacy.py`
  - Legacy-compatible plugins:
    - `excel_cli` inventory
    - `csv_cli` inventory
    - `json_cli` inventory
    - `legacy_network_task` task
    - `excel_results` output

## Runtime Flow

Current `main.py` now follows:

1. `load_inventory(<plugin by file extension>)`
2. `run_task(legacy_network_task)`
3. `write_output(excel_results)`

The old user-visible behavior is still preserved:

- action menu (`inspection`, `backup`, `inspection+backup`)
- custom command mode
- run summary, confirmation, dashboard, and result summary

## Why This Is a Draft

- Task plugin still wraps `NetworkInspector` directly (legacy adapter).
- Output is still fixed to Excel.
- Plugin selection is currently extension-based (`.xlsx/.xls/.xlsm`, `.csv`, `.json`).

## Inventory Examples

- `examples/inventory/devices.csv`
- `examples/inventory/devices.json`
- `examples/inventory/devices_wrapped.json`

## Next Migration Steps

1. Add plugin selection in `settings.yaml` (`inventory_plugin`, `task_plugin`, `output_plugin`).
2. Add `json` output plugin (inventory side is already available for `csv/json`).
3. Split legacy task plugin into dedicated task plugins:
   - `inspection_task`
   - `backup_task`
   - `custom_commands_task`
4. Add integration tests comparing legacy and plugin outputs for the same inputs.
