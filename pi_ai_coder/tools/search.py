"""Code search tool.

Prefers ripgrep (``rg``) when available -- fast, respects common ignore
files, and does the recursive directory walking for us. Falls back to a
plain Python directory walk + substring/regex search when ``rg`` isn't
installed, so the agent's search_code tool works either way.

Results are always capped -- this tool exists specifically so the agent
doesn't need "read every file" / a giant context window to find things.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from pi_ai_coder.tools.base import RiskLevel, ToolResult

DEFAULT_MAX_RESULTS = 50
DEFAULT_TIMEOUT = 15.0


class SearchTool:
    risk_level = RiskLevel.READ

    def __init__(self, project_root: Optional[str] = None, should_ignore: Optional[Callable[[Path], bool]] = None):
        self.project_root = str(Path(project_root or Path.cwd()).resolve())
        self._should_ignore = should_ignore or (lambda p: False)

    def search(
        self,
        query: str,
        glob: Optional[str] = None,
        directory: str = ".",
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="`query` must not be empty")

        search_dir = (Path(self.project_root) / directory).resolve()
        try:
            search_dir.relative_to(Path(self.project_root).resolve())
        except ValueError:
            return ToolResult(success=False, error=f"Path escapes project root: {directory}")
        if not search_dir.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {directory}")

        if self._has_ripgrep():
            return self._search_with_rg(query, glob, search_dir, max_results)
        return self._search_with_python(query, glob, search_dir, max_results)

    def _has_ripgrep(self) -> bool:
        try:
            subprocess.run(["rg", "--version"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _search_with_rg(self, query: str, glob: Optional[str], search_dir: Path, max_results: int) -> ToolResult:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never", "--max-count", "1000"]
        if glob:
            cmd.extend(["--glob", glob])
        cmd.extend([query, "."])

        try:
            result = subprocess.run(
                cmd,
                cwd=str(search_dir),
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Search timed out after {DEFAULT_TIMEOUT:.0f}s")

        # rg exit code 1 = no matches (not an error); >1 = real error
        if result.returncode > 1:
            return ToolResult(success=False, error=result.stderr.strip() or "ripgrep failed")

        lines = [l for l in result.stdout.splitlines() if l.strip()]
        truncated = len(lines) > max_results
        lines = lines[:max_results]
        output = "\n".join(lines)
        if truncated:
            output += f"\n... (truncated at {max_results} results)"

        return ToolResult(success=True, output=output, data={"count": len(lines), "truncated": truncated})

    def _search_with_python(self, query: str, glob: Optional[str], search_dir: Path, max_results: int) -> ToolResult:
        import fnmatch

        try:
            pattern = re.compile(re.escape(query))
        except re.error as exc:
            return ToolResult(success=False, error=f"Invalid search query: {exc}")

        matches: List[str] = []
        truncated = False

        import os
        for dirpath, dirnames, filenames in os.walk(search_dir):
            dirnames[:] = [d for d in dirnames if not self._should_ignore(Path(dirpath) / d)]
            for fname in sorted(filenames):
                fpath = Path(dirpath) / fname
                if self._should_ignore(fpath):
                    continue
                if glob and not fnmatch.fnmatch(fname, glob):
                    continue
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if pattern.search(line):
                        rel = fpath.relative_to(search_dir)
                        matches.append(f"{rel}:{lineno}:{line.strip()}")
                        if len(matches) >= max_results:
                            truncated = True
                            break
                if truncated:
                    break
            if truncated:
                break

        output = "\n".join(matches)
        if truncated:
            output += f"\n... (truncated at {max_results} results)"

        return ToolResult(success=True, output=output, data={"count": len(matches), "truncated": truncated})
