"""Top status bar: project, model, and generation state."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    def update_status(self, project_name: str, model_name: str, status_text: str) -> None:
        self.update(
            f"[bold]PI-AI-CODER[/bold]   "
            f"[dim]project:[/dim] {project_name}   "
            f"[dim]model:[/dim] {model_name}   "
            f"[yellow]{status_text}[/yellow]"
        )
