"""Read-only file preview screen.

Not an editor -- selecting a file shows it with line numbers and basic
syntax highlighting where Textual/Rich makes that easy. From here the user
can toggle whether the file is in the AI context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static, TextArea

_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".html": "html",
    ".css": "css",
    ".xml": "xml",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
}


class PreviewScreen(Screen):
    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Close"),
        Binding("a", "add_to_context", "Add to context"),
        Binding("d", "remove_from_context", "Remove from context"),
    ]

    def __init__(self, path: str, content: str, in_context: bool):
        super().__init__()
        self.path = path
        self.content = content
        self.in_context = in_context

    def compose(self) -> ComposeResult:
        yield Static(self._header_text(), id="preview-header")
        language: Optional[str] = _LANGUAGE_BY_SUFFIX.get(Path(self.path).suffix.lower())
        yield TextArea(
            self.content,
            language=language,
            read_only=True,
            show_line_numbers=True,
            id="preview-body",
        )
        yield Footer()

    def _header_text(self) -> str:
        marker = "[green]✓ in context[/green]" if self.in_context else "[dim]not in context[/dim]"
        return f"[bold]{self.path}[/bold]   {marker}   [dim](a: add · d: remove · esc: close)[/dim]"

    def action_add_to_context(self) -> None:
        self.app.request_context_toggle(self.path, True)
        self.in_context = True
        self.query_one("#preview-header", Static).update(self._header_text())

    def action_remove_from_context(self) -> None:
        self.app.request_context_toggle(self.path, False)
        self.in_context = False
        self.query_one("#preview-header", Static).update(self._header_text())
