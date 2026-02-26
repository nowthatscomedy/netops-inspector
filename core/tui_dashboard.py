from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class TuiDashboard:
    """네트워크 작업 진행 상태를 실시간으로 보여주는 TUI 대시보드."""

    def __init__(self, mode: str, total_devices: int) -> None:
        self.mode = mode
        self.total_devices = total_devices
        self.completed = 0
        self.success = 0
        self.fail = 0
        self.started_at = datetime.now()
        self.recent_logs: deque[str] = deque(maxlen=12)
        self._live: Live | None = None
        self._lock = threading.Lock()
        self._completed = False
        self._last_updated_at = self.started_at
        self._log_handler: _DashboardLogHandler | None = None
        self._saved_console_handlers: list[logging.Handler] = []

    def start(self) -> None:
        if self._live is not None:
            return
        self._live = Live(self._render(), refresh_per_second=5, transient=False)
        self._live.start()
        self._attach_log_handler()

    def mark_completed(self, note: str = "작업 완료") -> None:
        with self._lock:
            self._completed = True
            self.recent_logs.append(note)
            self._refresh()

    def stop(self) -> None:
        self._detach_log_handler()
        if self._live is None:
            return
        self._live.stop()
        self._live = None

    def _attach_log_handler(self) -> None:
        root = logging.getLogger()
        self._log_handler = _DashboardLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(
            logging.Formatter("[%(threadName)s] %(levelname)s | %(message)s")
        )
        self._saved_console_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        for h in self._saved_console_handlers:
            root.removeHandler(h)
        root.addHandler(self._log_handler)

    def _detach_log_handler(self) -> None:
        root = logging.getLogger()
        if self._log_handler is not None:
            root.removeHandler(self._log_handler)
            self._log_handler = None
        for h in self._saved_console_handlers:
            root.addHandler(h)
        self._saved_console_handlers = []

    def handle_event(self, event: dict[str, object]) -> None:
        with self._lock:
            event_type = str(event.get("type", ""))

            if event_type == "device_complete":
                if event.get("success"):
                    self.success += 1
                else:
                    self.fail += 1
                self.completed = self.success + self.fail
                self._last_updated_at = datetime.now()
                self._refresh()
                return

            message = str(event.get("message", ""))
            if not message:
                return
            self._last_updated_at = datetime.now()
            self.recent_logs.append(message)
            self._refresh()

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)

    @staticmethod
    def _bar(done: int, total: int, width: int = 28) -> Text:
        if total <= 0:
            return Text("0/0 (0%)")
        ratio = max(0.0, min(1.0, done / total))
        percent = int(ratio * 100)
        safe_done = max(0, min(done, total))
        filled = int(width * ratio)
        empty = width - filled
        bar = Text()
        bar.append("[", style="dim")
        if filled > 0:
            bar.append("█" * filled, style="bold green")
        if empty > 0:
            bar.append("░" * empty, style="grey50")
        bar.append("]", style="dim")
        bar.append(f" {safe_done}/{total} ({percent}%)", style="bold")
        return bar

    @staticmethod
    def _format_success_fail(success: int, fail: int, completed: int) -> Text:
        text = Text()
        text.append(str(success), style="bold green")
        text.append(" 성공", style="green")
        text.append(" / ", style="dim")
        text.append(str(fail), style="bold red")
        text.append(" 실패", style="red")
        if completed > 0:
            rate = success / completed * 100.0
            text.append("  (", style="dim")
            if rate >= 80:
                text.append(f"{rate:.1f}%", style="bold green")
            elif rate >= 50:
                text.append(f"{rate:.1f}%", style="bold yellow")
            else:
                text.append(f"{rate:.1f}%", style="bold red")
            text.append(")", style="dim")
        return text

    def _render(self) -> Group:
        elapsed = datetime.now() - self.started_at
        elapsed_seconds = max(1.0, elapsed.total_seconds())
        completed = max(0, self.completed)
        remaining = max(0, self.total_devices - completed)
        throughput_per_min = (completed / elapsed_seconds) * 60.0

        if self._completed:
            status_text = Text("● 완료", style="bold green")
        elif completed > 0:
            status_text = Text("● 진행 중", style="bold yellow")
        else:
            status_text = Text("● 준비 중", style="bold cyan")

        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="cyan")
        summary.add_column(style="bold")
        summary.add_row("모드", self.mode)
        summary.add_row("상태", status_text)
        summary.add_row("경과 시간", str(elapsed).split(".")[0])
        summary.add_row("장비 진행", self._bar(self.completed, self.total_devices))
        summary.add_row("성공/실패", self._format_success_fail(self.success, self.fail, completed))
        summary.add_row("남은 장비", Text(str(remaining), style="bold cyan"))
        summary.add_row("처리 속도", Text(f"{throughput_per_min:.2f} 대/분", style="bold magenta"))
        summary.add_row("마지막 업데이트", self._last_updated_at.strftime("%H:%M:%S"))

        event_lines = "\n".join(self.recent_logs) if self.recent_logs else "아직 이벤트가 없습니다."
        event_text = Text(event_lines, overflow="ellipsis")
        return Group(
            Panel(summary, title="[bold green]실시간 작업 대시보드[/bold green]", border_style="green"),
            Panel(event_text, title="[bold cyan]최근 이벤트[/bold cyan]", border_style="cyan"),
        )


class _DashboardLogHandler(logging.Handler):
    """대시보드가 활성화된 동안 로그 레코드를 패널로 전달하는 핸들러."""

    def __init__(self, dashboard: TuiDashboard) -> None:
        super().__init__()
        self._dashboard = dashboard

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self._dashboard.handle_event({"type": "log", "message": message})
        except Exception:
            self.handleError(record)
