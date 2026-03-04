from __future__ import annotations

from core.plugin_platform.contracts import (
    InventoryLoadError,
    InventoryPayload,
    OutputRequest,
    OutputWriteError,
    TaskExecutionError,
    TaskRequest,
    TaskResult,
)
from core.plugin_platform.registry import PluginRegistry
from core.settings import AppSettings


class PluginRuntime:
    """Thin runtime that dispatches to registered plugins."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    def load_inventory(
        self,
        plugin_name: str,
        *,
        settings: AppSettings,
        options: dict | None = None,
    ) -> InventoryPayload:
        try:
            plugin = self.registry.get_inventory(plugin_name)
            return plugin.load(settings=settings, options=options)
        except InventoryLoadError:
            raise
        except Exception as exc:
            raise InventoryLoadError(str(exc)) from exc

    def run_task(self, plugin_name: str, request: TaskRequest) -> TaskResult:
        try:
            plugin = self.registry.get_task(plugin_name)
            return plugin.run(request)
        except TaskExecutionError:
            raise
        except Exception as exc:
            raise TaskExecutionError(str(exc)) from exc

    def write_output(self, plugin_name: str, request: OutputRequest) -> None:
        try:
            plugin = self.registry.get_output(plugin_name)
            plugin.write(request)
        except OutputWriteError:
            raise
        except Exception as exc:
            raise OutputWriteError(str(exc)) from exc
