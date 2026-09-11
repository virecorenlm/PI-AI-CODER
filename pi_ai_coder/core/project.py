"""Resolves and validates the active project/workspace root.

There are two distinct roots in PI-AI-CODER:

* the *application* root -- wherever PI-AI-CODER itself is installed/checked
  out (irrelevant to project operations; only provider/model config may
  reasonably come from here or from user-level config).
* the *project* root -- the user's active coding workspace, resolved from
  the current working directory at launch time (or an explicit
  ``--project`` override).

Every project-oriented operation (file tree, context, git, shell cwd,
session persistence, path-safety checks, file writes) must resolve from the
project root -- never from ``Path.cwd()`` scattered across call sites, and
never from the application's own install directory.
"""

from __future__ import annotations

from pathlib import Path


class ProjectRootError(ValueError):
    """Raised when a requested project root path doesn't exist or isn't a directory."""


def resolve_project_root(raw_path: str = ".") -> Path:
    """Resolve ``raw_path`` (relative, ``~``, or absolute) to an existing directory.

    Relative paths resolve against the current working directory at call
    time -- so ``resolve_project_root(".")`` (the default) is "wherever the
    user launched PI-AI-CODER from," independent of where PI-AI-CODER is
    installed.
    """
    root = Path(raw_path).expanduser().resolve()

    if not root.exists():
        raise ProjectRootError(f"Project path does not exist: {root}")
    if not root.is_dir():
        raise ProjectRootError(f"Project path is not a directory: {root}")

    return root
