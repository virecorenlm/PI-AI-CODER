"""Git status pane.

Read-only display of branch + working tree status. Diffs are shown in the
tool output pane when requested. No destructive or write git operations are
ever issued from here.
"""

from __future__ import annotations

from typing import List, Optional

from textual.widgets import Static

from pi_ai_coder.tools.git import GitFileStatus


class GitPanel(Static):
    can_focus = True

    def update_status(self, branch: Optional[str], statuses: List[GitFileStatus], is_repo: bool = True) -> None:
        lines = ["[bold]GIT[/bold]"]

        if not is_repo:
            lines.append("  [dim]not a git repository[/dim]")
            self.update("\n".join(lines))
            return

        lines.append(f"branch: {branch or '(detached)'}")

        if not statuses:
            lines.append("  [green](clean)[/green]")
        else:
            for s in statuses[:20]:
                if s.is_untracked:
                    marker, color = "?", "yellow"
                elif s.is_staged:
                    marker, color = (s.index_status.strip() or "M"), "green"
                else:
                    marker, color = (s.worktree_status.strip() or "M"), "yellow"
                lines.append(f"  [{color}]{marker}[/{color}] {s.path}")
            if len(statuses) > 20:
                lines.append(f"  [dim]… +{len(statuses) - 20} more[/dim]")

        self.update("\n".join(lines))
