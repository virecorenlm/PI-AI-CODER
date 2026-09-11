"""Shared tool primitives: risk levels, results, and safe path resolution.

This is the foundation for the future permission system described in
CLAUDE.md: every tool declares a ``RiskLevel`` so a permission layer can
later decide what may run automatically vs. what needs user approval.
Nothing here grants autonomy -- it only makes the risk explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class RiskLevel(Enum):
    READ = "read"                # safe to run automatically inside the project
    WRITE = "write"               # requires clear user intent
    EXECUTE = "execute"           # arbitrary command execution
    DESTRUCTIVE = "destructive"   # never automatic; always requires explicit approval


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    exit_code: Optional[int] = None
    duration: Optional[float] = None
    data: Dict[str, Any] = field(default_factory=dict)


class PathOutsideProjectError(ValueError):
    """Raised when a path would resolve outside the project boundary."""


def resolve_within_project(path: str, project_root: str) -> Path:
    """Resolve ``path`` (relative or absolute) and ensure it stays inside
    ``project_root``. Uses ``Path.resolve()`` so ``..`` segments and
    symlinks are accounted for, not just string prefixes.
    """
    root = Path(project_root).resolve()
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathOutsideProjectError(f"Path escapes project root: {path}") from None

    return resolved
