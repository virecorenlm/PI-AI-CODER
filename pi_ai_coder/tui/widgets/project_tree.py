"""Project file explorer.

Built on Textual's built-in ``DirectoryTree`` so directories are only
expanded (and their contents read) on demand -- we never recursively load
the whole project into memory just to display it. Ignored paths (per
``ContextManager.should_ignore``) are filtered out, and files currently in
the AI context get a checkmark.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.widgets.tree import TreeNode

from pi_ai_coder.context.manager import ContextManager


class ProjectTree(DirectoryTree):
    """A DirectoryTree that hides ignored paths and marks context files."""

    BINDINGS = [
        Binding("a", "add_to_context", "Add to context"),
        Binding("d", "remove_from_context", "Remove from context"),
    ]

    class ContextToggleRequested(Message):
        def __init__(self, path: str, add: bool) -> None:
            self.path = path
            self.add = add
            super().__init__()

    def __init__(self, path: str, context_manager: ContextManager, **kwargs):
        super().__init__(path, **kwargs)
        self.context_manager = context_manager
        self.context_files: Set[str] = set()

    def action_add_to_context(self) -> None:
        node = self.cursor_node
        if node is not None and node.data is not None and node.data.path.is_file():
            self.post_message(self.ContextToggleRequested(str(node.data.path), True))

    def action_remove_from_context(self) -> None:
        node = self.cursor_node
        if node is not None and node.data is not None and node.data.path.is_file():
            self.post_message(self.ContextToggleRequested(str(node.data.path), False))

    def set_context_files(self, paths: Iterable[str]) -> None:
        self.context_files = {str(Path(p).resolve()) for p in paths}
        self.refresh()

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if not self.context_manager.should_ignore(p)]

    def render_label(self, node: TreeNode[DirEntry], base_style, style) -> Text:
        label = super().render_label(node, base_style, style)
        if node.data is not None:
            try:
                resolved = str(node.data.path.resolve())
            except OSError:
                resolved = str(node.data.path)
            if resolved in self.context_files:
                label = Text("✓ ") + label
        return label
