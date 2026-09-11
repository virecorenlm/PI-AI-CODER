"""File tool: reading and writing files, constrained to the project boundary.

Reads (and directory listing/search) are READ-risk and allowed
automatically. Writes (save/create/patch/delete/move) are WRITE-risk and
must only happen in response to clear, explicit user intent (the ``save``
command, an approved agent action) -- callers are responsible for that
intent check; this tool only enforces the *path safety* boundary, which
applies unconditionally (``..``, absolute paths, and symlinks are all
resolved and checked -- a model-generated path can never silently escape
the project root through this tool).
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Callable, List, Optional

from pi_ai_coder.tools.base import PathOutsideProjectError, RiskLevel, ToolResult, resolve_within_project


def _unified_diff(old_text: str, new_text: str, path: str) -> str:
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


class FileTool:
    read_risk_level = RiskLevel.READ
    write_risk_level = RiskLevel.WRITE

    def __init__(self, project_root: Optional[str] = None, should_ignore: Optional[Callable[[Path], bool]] = None):
        self.project_root = str(Path(project_root or Path.cwd()).resolve())
        self._should_ignore = should_ignore or (lambda p: False)

    def _resolve(self, path: str) -> tuple:
        """Returns (resolved_path, error_result_or_None)."""
        try:
            return resolve_within_project(path, self.project_root), None
        except PathOutsideProjectError as exc:
            return None, ToolResult(success=False, error=str(exc))

    # -- reading ------------------------------------------------------------

    def read_text(self, path: str, max_size_kb: int = 2048) -> ToolResult:
        resolved, err = self._resolve(path)
        if err:
            return err

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

    def read_file_range(self, path: str, start_line: int, end_line: int, max_size_kb: int = 2048) -> ToolResult:
        result = self.read_text(path, max_size_kb=max_size_kb)
        if not result.success:
            return result

        lines = result.output.splitlines()
        start = max(1, int(start_line))
        end = min(len(lines), int(end_line))
        if start > end:
            return ToolResult(success=False, error=f"Invalid range: start_line ({start}) > end_line ({end})")

        snippet = "\n".join(lines[start - 1:end])
        return ToolResult(
            success=True,
            output=snippet,
            data={"path": result.data["path"], "start_line": start, "end_line": end, "total_lines": len(lines)},
        )

    def list_directory(self, path: str = ".") -> ToolResult:
        resolved, err = self._resolve(path)
        if err:
            return err

        if not resolved.exists():
            return ToolResult(success=False, error=f"Directory not found: {path}")
        if not resolved.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")

        entries = []
        for child in sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if self._should_ignore(child):
                continue
            kind = "dir" if child.is_dir() else "file"
            entries.append(f"{kind}\t{child.name}")

        return ToolResult(success=True, output="\n".join(entries), data={"path": str(resolved)})

    def find_files(self, pattern: str = "*", directory: str = ".", max_results: int = 100) -> ToolResult:
        import fnmatch

        resolved, err = self._resolve(directory)
        if err:
            return err

        if not resolved.exists():
            return ToolResult(success=False, error=f"Directory not found: {directory}")
        if not resolved.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {directory}")

        root_path = Path(self.project_root)
        matches: List[str] = []
        truncated = False

        for dirpath, dirnames, filenames in os.walk(resolved):
            dirnames[:] = [d for d in dirnames if not self._should_ignore(Path(dirpath) / d)]
            for fname in sorted(filenames):
                fpath = Path(dirpath) / fname
                if self._should_ignore(fpath):
                    continue
                if fnmatch.fnmatch(fname, pattern):
                    matches.append(str(fpath.relative_to(root_path)))
                    if len(matches) >= max_results:
                        truncated = True
                        break
            if truncated:
                break

        output = "\n".join(matches)
        if truncated:
            output += f"\n... (truncated at {max_results} results)"

        return ToolResult(success=True, output=output, data={"count": len(matches), "truncated": truncated})

    # -- writing --------------------------------------------------------------

    def save(self, path: str, content: str, restrict_to_project: bool = True) -> ToolResult:
        """Write ``content`` to ``path`` (create or full overwrite).

        ``restrict_to_project`` defaults to True (the safe default for any
        automated/agent-driven write). The CLI's ``save`` command passes
        ``restrict_to_project=False`` because the user directly typed that
        exact destination path -- CLAUDE.md's project-boundary rule only
        restricts writes that weren't explicitly requested.
        """
        if restrict_to_project:
            resolved, err = self._resolve(path)
            if err:
                return err
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

    def create_file(self, path: str, content: str = "") -> ToolResult:
        """Create a brand-new file. Fails if it already exists (use
        ``save``/``apply_patch`` to modify an existing file intentionally)."""
        resolved, err = self._resolve(path)
        if err:
            return err

        if resolved.exists():
            return ToolResult(success=False, error=f"File already exists: {path} (use apply_patch or write_file to modify it)")

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not create {path}: {exc}")

        return ToolResult(success=True, output=f"Created {path}", data={"path": str(resolved)})

    def apply_patch(self, path: str, edits: List[dict]) -> ToolResult:
        """Apply a list of exact-match search/replace edits to an existing file.

        Each edit is ``{"old": "...", "new": "..."}``. ``old`` must occur
        exactly once in the file's current content (after any earlier edits
        in this same call have been applied) -- zero matches or ambiguous
        (multiple) matches both fail cleanly with no changes written, so the
        caller can reread the file and retry with more context, rather than
        the tool guessing. This covers replace/insert/remove/rewrite-a-span
        without needing line-numbered diff hunks.
        """
        resolved, err = self._resolve(path)
        if err:
            return err

        if not resolved.exists():
            return ToolResult(success=False, error=f"File not found: {path} (use create_file for new files)")
        if not resolved.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        if not isinstance(edits, list) or not edits:
            return ToolResult(success=False, error="`edits` must be a non-empty list of {old, new} objects")

        try:
            original = resolved.read_text(encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not read {path}: {exc}")

        working = original
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict) or "old" not in edit or "new" not in edit:
                return ToolResult(success=False, error=f"Edit {i}: must have 'old' and 'new' string fields")
            old, new = edit["old"], edit["new"]
            if not isinstance(old, str) or not isinstance(new, str):
                return ToolResult(success=False, error=f"Edit {i}: 'old'/'new' must be strings")
            if old == "":
                return ToolResult(success=False, error=f"Edit {i}: 'old' must not be empty")

            count = working.count(old)
            if count == 0:
                return ToolResult(
                    success=False,
                    error=f"Edit {i}: text not found in {path} -- the file may have changed; reread it and try again",
                )
            if count > 1:
                return ToolResult(
                    success=False,
                    error=f"Edit {i}: text matched {count} times in {path} -- provide more surrounding context to make it unique",
                )
            working = working.replace(old, new, 1)

        if working == original:
            return ToolResult(success=False, error="Patch made no changes")

        try:
            resolved.write_text(working, encoding="utf-8")
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not write {path}: {exc}")

        diff = _unified_diff(original, working, path)
        return ToolResult(success=True, output=f"Patched {path}", data={"path": str(resolved), "diff": diff})

    def delete_file(self, path: str) -> ToolResult:
        """Delete a single file. Refuses to delete directories -- bulk
        deletion is a destructive operation that must go through an
        explicitly-approved shell command, not this tool."""
        resolved, err = self._resolve(path)
        if err:
            return err

        if not resolved.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not resolved.is_file():
            return ToolResult(success=False, error=f"Not a file (refusing to delete directories): {path}")

        try:
            resolved.unlink()
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not delete {path}: {exc}")

        return ToolResult(success=True, output=f"Deleted {path}", data={"path": str(resolved)})

    def move_file(self, src: str, dst: str) -> ToolResult:
        resolved_src, err = self._resolve(src)
        if err:
            return err
        resolved_dst, err = self._resolve(dst)
        if err:
            return err

        if not resolved_src.exists():
            return ToolResult(success=False, error=f"Source not found: {src}")
        if resolved_dst.exists():
            return ToolResult(success=False, error=f"Destination already exists: {dst}")

        try:
            resolved_dst.parent.mkdir(parents=True, exist_ok=True)
            resolved_src.rename(resolved_dst)
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not move {src} -> {dst}: {exc}")

        return ToolResult(
            success=True,
            output=f"Moved {src} -> {dst}",
            data={"path": str(resolved_dst), "old_path": str(resolved_src)},
        )
