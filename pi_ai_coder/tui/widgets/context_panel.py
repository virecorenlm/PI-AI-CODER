"""Context management panel.

Shows manually selected context files (or the current auto-discovered set),
whether auto-context is on, and an approximate context size -- backed
directly by ``ContextManager``/``AssistantService`` state, nothing here
owns its own copy of the truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from textual.widgets import Static

from pi_ai_coder.context.manager import ContextManager


class ContextPanel(Static):
    def update_context(
        self,
        context_files: List[str],
        auto_context: bool,
        auto_discovered_files: Optional[List[str]] = None,
        context_chars: int = 0,
    ) -> None:
        lines = ["[bold]CONTEXT[/bold]"]

        if context_files:
            for f in context_files:
                lines.append(f"  [green]✓[/green] {Path(f).name}")
        elif auto_context and auto_discovered_files:
            lines.append("  [dim]auto-discovered:[/dim]")
            for f in auto_discovered_files[:8]:
                lines.append(f"  [dim]·[/dim] {Path(f).name}")
        else:
            lines.append("  [dim](no files selected)[/dim]")

        lines.append("")
        lines.append(f"Auto-context: {'[green]on[/green]' if auto_context else '[dim]off[/dim]'}")

        if context_chars:
            tokens = context_chars // ContextManager.AVG_CHARS_PER_TOKEN
            lines.append(f"~{context_chars} chars (~{tokens} tokens)")

        self.update("\n".join(lines))
