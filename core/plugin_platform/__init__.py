from core.plugin_platform.contracts import (
    InventoryLoadError,
    InventoryPayload,
    OutputRequest,
    OutputWriteError,
    TaskExecutionError,
    TaskRequest,
    TaskResult,
)
from core.plugin_platform.legacy import (
    CSV_INVENTORY_PLUGIN,
    CSV_OUTPUT_PLUGIN,
    EXCEL_INVENTORY_PLUGIN,
    JSON_INVENTORY_PLUGIN,
    JSON_OUTPUT_PLUGIN,
    LEGACY_INVENTORY_PLUGIN,
    LEGACY_OUTPUT_PLUGIN,
    LEGACY_TASK_PLUGIN,
    build_legacy_plugin_runtime,
)
from core.plugin_platform.runtime import PluginRuntime

__all__ = [
    "InventoryLoadError",
    "InventoryPayload",
    "OutputRequest",
    "OutputWriteError",
    "TaskExecutionError",
    "TaskRequest",
    "TaskResult",
    "CSV_INVENTORY_PLUGIN",
    "CSV_OUTPUT_PLUGIN",
    "EXCEL_INVENTORY_PLUGIN",
    "JSON_INVENTORY_PLUGIN",
    "JSON_OUTPUT_PLUGIN",
    "LEGACY_INVENTORY_PLUGIN",
    "LEGACY_OUTPUT_PLUGIN",
    "LEGACY_TASK_PLUGIN",
    "PluginRuntime",
    "build_legacy_plugin_runtime",
]
