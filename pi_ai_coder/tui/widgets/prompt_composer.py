"""Multiline prompt input.

Enter inserts a newline (normal TextArea behavior); Ctrl+Enter submits.
Most terminals deliver Ctrl+Enter as the same sequence as Ctrl+J, so that's
the primary binding -- see the help screen (F1) for details. Ctrl+Up/Down
walk prompt history; Escape blurs back to the rest of the workspace.
"""

from __future__ import annotations

from typing import List

from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


class PromptSubmitted(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class PromptComposer(TextArea):
    BINDINGS = [
        Binding("ctrl+j", "submit", "Submit", priority=True),
        Binding("ctrl+up", "history_prev", "Prev prompt"),
        Binding("ctrl+down", "history_next", "Next prompt"),
        Binding("escape", "blur_composer", "Unfocus"),
    ]

    def __init__(self, **kwargs):
        kwargs.setdefault("show_line_numbers", False)
        super().__init__(**kwargs)
        # NOTE: TextArea already owns an attribute named `history` (its own
        # undo/redo edit history) -- do not shadow it here.
        self.prompt_history: List[str] = []
        self._history_index: int = 0
        self._draft: str = ""

    def set_history(self, history: List[str]) -> None:
        self.prompt_history = list(history)
        self._history_index = len(self.prompt_history)

    def action_submit(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.post_message(PromptSubmitted(text))
        self.prompt_history.append(text)
        self._history_index = len(self.prompt_history)
        self.clear()

    def action_history_prev(self) -> None:
        if not self.prompt_history:
            return
        if self._history_index == len(self.prompt_history):
            self._draft = self.text
        if self._history_index > 0:
            self._history_index -= 1
            self.text = self.prompt_history[self._history_index]
            self.move_cursor(self.document.end)

    def action_history_next(self) -> None:
        if not self.prompt_history:
            return
        if self._history_index < len(self.prompt_history) - 1:
            self._history_index += 1
            self.text = self.prompt_history[self._history_index]
        else:
            self._history_index = len(self.prompt_history)
            self.text = self._draft
        self.move_cursor(self.document.end)

    def action_blur_composer(self) -> None:
        if self.screen is not None:
            self.screen.set_focus(None)
