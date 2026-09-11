"""File tool: reading and writing files, constrained to the project boundary.

Reads are READ-risk and allowed automatically. Writes are WRITE-risk and
must only happen in response to clear, explicit user intent (the ``save``
command, or a future approved model-write) -- callers are responsible for
that intent check; this tool only enforces the *path safety* boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pi_ai_coder.tools.base import PathOutsideProjectError, RiskLevel, ToolResult, resolve_within_project


class FileTool:
    read_risk_level = RiskLevel.READ
    write_risk_level = RiskLevel.WRITE

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = str(Path(project_root or Path.cwd()).resolve())

    def read_text(self, path: str, max_size_kb: int = 2048) -> ToolResult:
        try:
            resolved = resolve_within_project(path, self.project_root)
        except PathOutsideProjectError as exc:
            return ToolResult(success=False, error=str(exc))

        if not resolved.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not resolved.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        if resolved.stat().st_size > max_size_kb * 1024:
            return ToolResult(success=False, error=f"File too large to preview (> {max_size_kb} KB): {path}")

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not read {path}: {exc}")

        return ToolResult(success=True, output=content, data={"path": str(resolved)})

    def save(self, path: str, content: str, restrict_to_project: bool = True) -> ToolResult:
        """Write ``content`` to ``path``. Requires the caller to already have
        established clear user intent (this only enforces path safety).

        ``restrict_to_project`` defaults to True (the safe default for any
        future automated/model-driven write). The CLI's ``save`` command
        passes ``restrict_to_project=False`` because the user directly typed
        that exact destination path -- CLAUDE.md's project-boundary rule
        only restricts writes that weren't explicitly requested.
        """
        if restrict_to_project:
            try:
                resolved = resolve_within_project(path, self.project_root)
            except PathOutsideProjectError as exc:
                return ToolResult(success=False, error=str(exc))
        else:
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = Path(self.project_root) / resolved

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not write {path}: {exc}")

        return ToolResult(success=True, output=f"Saved to {resolved}", data={"path": str(resolved)})
