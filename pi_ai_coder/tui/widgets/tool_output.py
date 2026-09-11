"""Tool / terminal output pane.

Displays shell command and other tool activity so it's visually distinct
from model conversation text. Not a full terminal emulator -- it shows
command, streamed stdout/stderr, exit code, and duration.
"""

from __future__ import annotations

from typing import Optional

from textual.widgets import RichLog


class ToolOutput(RichLog):
    def __init__(self, **kwargs):
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("highlight", False)
        kwargs.setdefault("markup", True)
        kwargs.setdefault("max_lines", 2000)
        super().__init__(**kwargs)

    def command_header(self, command: str) -> None:
        self.write(f"[bold cyan]$ {command}[/bold cyan]")

    def line(self, text: str) -> None:
        self.write(text)

    def command_footer(self, exit_code: Optional[int], duration: Optional[float]) -> None:
        color = "green" if exit_code == 0 else "red"
        code_display = "?" if exit_code is None else str(exit_code)
        parts = [f"[dim]exit code:[/dim] [{color}]{code_display}[/{color}]"]
        if duration is not None:
            parts.append(f"[dim]({duration:.2f}s)[/dim]")
        self.write(" ".join(parts))
        self.write("")
