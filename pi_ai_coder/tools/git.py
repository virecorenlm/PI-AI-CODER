"""Git tool: read-only status/diff/log/branch helpers.

Only ever shells out to safe, read-only git subcommands (status, diff, log,
branch, rev-parse). Nothing here ever writes to the repository -- no
commit, reset, checkout, clean, push, merge or rebase. Those, if ever
added, must be explicit user-initiated actions per CLAUDE.md's Git Safety
section, never automatic.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional

from pi_ai_coder.tools.base import RiskLevel, ToolResult

_STATUS_LABELS = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "unmerged",
    "?": "untracked",
    " ": "",
}


@dataclass
class GitFileStatus:
    path: str
    index_status: str   # staged status code
    worktree_status: str  # unstaged status code

    @property
    def is_untracked(self) -> bool:
        return self.index_status == "?" and self.worktree_status == "?"

    @property
    def is_staged(self) -> bool:
        return self.index_status not in (" ", "?")

    def describe(self) -> str:
        if self.is_untracked:
            return "untracked"
        parts = []
        if self.is_staged:
            parts.append(f"staged:{_STATUS_LABELS.get(self.index_status, self.index_status)}")
        if self.worktree_status not in (" ", "?"):
            parts.append(_STATUS_LABELS.get(self.worktree_status, self.worktree_status))
        return ", ".join(parts) or "unchanged"


class GitTool:
    risk_level = RiskLevel.READ

    def __init__(self, cwd: Optional[str] = None):
        self.cwd = cwd

    def _run(self, args: List[str], timeout: float = 15.0) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=timeout,
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
            )
        except FileNotFoundError:
            return ToolResult(success=False, error="git is not installed")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="git command timed out")

    def is_repo(self) -> bool:
        return self._run(["rev-parse", "--is-inside-work-tree"]).success

    def current_branch(self) -> Optional[str]:
        result = self._run(["branch", "--show-current"])
        if result.success:
            branch = result.output.strip()
            return branch or None
        return None

    def status(self) -> List[GitFileStatus]:
        """Parse `git status --porcelain=v1` into structured entries."""
        result = self._run(["status", "--porcelain=v1"])
        if not result.success:
            return []

        entries = []
        for line in result.output.splitlines():
            if not line:
                continue
            index_status, worktree_status = line[0], line[1]
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            entries.append(GitFileStatus(path=path, index_status=index_status, worktree_status=worktree_status))
        return entries

    def diff(self, path: Optional[str] = None, staged: bool = False) -> ToolResult:
        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            args.extend(["--", path])
        return self._run(args)

    def log(self, max_count: int = 10) -> ToolResult:
        return self._run(["log", f"-{max_count}", "--oneline"])
