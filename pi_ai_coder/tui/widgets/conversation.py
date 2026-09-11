"""The main conversation/agent panel.

Shows user messages, streaming assistant messages, tool activity, errors,
and system/status notices, with Markdown + fenced code block rendering.
"""

from __future__ import annotations

from typing import Optional

from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static


class ConversationView(VerticalScroll):
    """Scrollable log of the conversation, rendered as Markdown blocks."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._assistant_widget: Optional[Markdown] = None
        self._assistant_text: str = ""

    def add_user_message(self, text: str) -> None:
        self._assistant_widget = None
        self.mount(Markdown(f"**You**\n\n{text}", classes="message user-message"))
        self.scroll_end(animate=False)

    def start_assistant_message(self) -> None:
        self._assistant_text = ""
        widget = Markdown("**AI**\n\n_thinking..._", classes="message assistant-message")
        self._assistant_widget = widget
        self.mount(widget)
        self.scroll_end(animate=False)

    def append_assistant_token(self, text: str) -> None:
        if self._assistant_widget is None:
            self.start_assistant_message()
        self._assistant_text += text
        self._assistant_widget.update(f"**AI**\n\n{self._assistant_text}")
        self.scroll_end(animate=False)

    def finish_assistant_message(self) -> None:
        if self._assistant_widget is not None and not self._assistant_text.strip():
            self._assistant_widget.update("**AI**\n\n_(empty response)_")
        self._assistant_widget = None

    def add_system_message(self, text: str) -> None:
        self.mount(Static(f"[dim]· {text}[/dim]", classes="message system-message"))
        self.scroll_end(animate=False)

    def add_tool_message(self, text: str) -> None:
        self.mount(Static(text, classes="message tool-message"))
        self.scroll_end(animate=False)

    def add_tool_action(self, text: str) -> None:
        """A compact "● Read src/auth.py" style agent-action marker."""
        self._assistant_widget = None
        self.mount(Static(f"[cyan]●[/cyan] {text}", classes="message tool-action"))
        self.scroll_end(animate=False)

    def add_tool_output(self, text: str) -> None:
        """Indented raw tool output (e.g. test results) under the most recent action."""
        indented = "\n".join(f"  {line}" for line in text.splitlines())
        self.mount(Static(f"[dim]{indented}[/dim]", classes="message tool-output"))
        self.scroll_end(animate=False)

    def add_error(self, text: str) -> None:
        self.mount(Static(f"[bold red]✗ {text}[/bold red]", classes="message error-message"))
        self.scroll_end(animate=False)

    def clear_conversation(self) -> None:
        self._assistant_widget = None
        self._assistant_text = ""
        self.remove_children()
