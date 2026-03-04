from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from core.settings import AppSettings

DeviceRecord = dict[str, Any]


class PluginRuntimeError(RuntimeError):
    """Base error for plugin runtime failures."""


class InventoryLoadError(PluginRuntimeError):
    """Raised when an inventory plugin cannot load devices."""


class TaskExecutionError(PluginRuntimeError):
    """Raised when a task plugin cannot execute a job."""


class OutputWriteError(PluginRuntimeError):
    """Raised when an output plugin cannot persist results."""


@dataclass(slots=True)
class InventoryPayload:
    source: str
    filepath: str
    devices: list[DeviceRecord]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskRequest:
    task_name: str
    run_timestamp: str
    settings: AppSettings
    devices: list[DeviceRecord]
    status_callback: Any | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskResult:
    task_name: str
    output_excel: str
    results: list[dict[str, Any]]
    backup_dir: str = ""
    session_log_dir: str = ""
    inspection_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OutputRequest:
    output_name: str
    settings: AppSettings
    task_result: TaskResult
    column_order: list[str] | None = None


class InventoryPlugin(Protocol):
    name: str

    def load(
        self,
        *,
        settings: AppSettings,
        options: dict[str, Any] | None = None,
    ) -> InventoryPayload: ...


class TaskPlugin(Protocol):
    name: str

    def run(self, request: TaskRequest) -> TaskResult: ...


class OutputPlugin(Protocol):
    name: str

    def write(self, request: OutputRequest) -> None: ...
