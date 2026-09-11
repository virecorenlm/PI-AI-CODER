"""Modal approval prompt for destructive agent tool calls.

Shown whenever the agent loop classifies a requested tool call as
DESTRUCTIVE (see ``pi_ai_coder.agent.permissions``) -- e.g. a shell command
matching a destructive pattern. Nothing destructive ever runs without the
user explicitly approving it here.
"""

from __future__ import annotations

from typing import Any, Dict

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from pi_ai_coder.agent.display import describe_tool_call


class ApprovalScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "approve", "Allow"),
        Binding("n,escape", "deny", "Deny"),
    ]

    def __init__(self, tool_name: str, arguments: Dict[str, Any]):
        super().__init__()
        self.tool_name = tool_name
        self.arguments = arguments

    def compose(self) -> ComposeResult:
        description = describe_tool_call(self.tool_name, self.arguments)
        detail = ""
        if self.tool_name in ("run_command", "run_tests"):
            detail = f"\n\n[bold]{self.arguments.get('command', '')}[/bold]"
        with Vertical(id="approval-dialog"):
            yield Static("[bold yellow]⚠ Approval required[/bold yellow]", id="approval-title")
            yield Static(f"{description}{detail}", id="approval-body")
            yield Static("[dim]This looks potentially destructive and needs your OK.[/dim]", id="approval-note")
            with Horizontal(id="approval-buttons"):
                yield Button("Deny (n)", id="approval-deny", variant="error")
                yield Button("Allow (y)", id="approval-allow", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approval-allow")

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)
