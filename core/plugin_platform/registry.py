from __future__ import annotations

from core.plugin_platform.contracts import InventoryPlugin, OutputPlugin, TaskPlugin


class PluginRegistry:
    """In-memory registry for inventory/task/output plugins."""

    def __init__(self) -> None:
        self._inventory: dict[str, InventoryPlugin] = {}
        self._tasks: dict[str, TaskPlugin] = {}
        self._outputs: dict[str, OutputPlugin] = {}

    def register_inventory(self, plugin: InventoryPlugin) -> None:
        if plugin.name in self._inventory:
            raise ValueError(f"Inventory plugin '{plugin.name}' is already registered.")
        self._inventory[plugin.name] = plugin

    def register_task(self, plugin: TaskPlugin) -> None:
        if plugin.name in self._tasks:
            raise ValueError(f"Task plugin '{plugin.name}' is already registered.")
        self._tasks[plugin.name] = plugin

    def register_output(self, plugin: OutputPlugin) -> None:
        if plugin.name in self._outputs:
            raise ValueError(f"Output plugin '{plugin.name}' is already registered.")
        self._outputs[plugin.name] = plugin

    def get_inventory(self, name: str) -> InventoryPlugin:
        if name not in self._inventory:
            raise KeyError(f"Unknown inventory plugin: {name}")
        return self._inventory[name]

    def get_task(self, name: str) -> TaskPlugin:
        if name not in self._tasks:
            raise KeyError(f"Unknown task plugin: {name}")
        return self._tasks[name]

    def get_output(self, name: str) -> OutputPlugin:
        if name not in self._outputs:
            raise KeyError(f"Unknown output plugin: {name}")
        return self._outputs[name]

    def list_inventory(self) -> tuple[str, ...]:
        return tuple(self._inventory.keys())

    def list_tasks(self) -> tuple[str, ...]:
        return tuple(self._tasks.keys())

    def list_outputs(self) -> tuple[str, ...]:
        return tuple(self._outputs.keys())
