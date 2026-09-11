"""Compact, human-readable descriptions of tool calls/results.

Shared by the CLI and the TUI so agent actions render consistently in both
("● Read src/auth.py", "● Patched src/auth.py", "● Running: pytest -q") --
this is presentation-only text formatting, not application logic, so both
frontends use it directly rather than each inventing their own phrasing.
"""

from __future__ import annotations

from typing import Any, Dict

_OPEN_TAG = "<tool_call>"


class LiveProseFilter:
    """Feed model token chunks in as they stream; get back the portion safe
    to display immediately as prose.

    Once a ``<tool_call>`` tag starts appearing in the accumulating text,
    further output is held back (so the raw tool-call JSON never flashes on
    screen) without needing a full incremental JSON parser -- the agent
    loop only ever acts on the first tool call in a turn anyway, so once a
    tag has started there is nothing further worth displaying live for that
    turn. A partial tag match at the trailing edge of a chunk (e.g. a chunk
    boundary lands inside "<tool_c|all>") is never emitted prematurely.
    """

    def __init__(self):
        self._buffer = ""
        self._sent_upto = 0
        self._suppressing = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        if self._suppressing:
            return ""

        open_idx = self._buffer.find(_OPEN_TAG, self._sent_upto)
        if open_idx != -1:
            visible = self._buffer[self._sent_upto:open_idx]
            self._sent_upto = open_idx
            self._suppressing = True
            return visible

        max_partial = len(_OPEN_TAG) - 1
        safe_end = len(self._buffer)
        tail_start = max(self._sent_upto, len(self._buffer) - max_partial)
        tail = self._buffer[tail_start:]
        for i in range(min(max_partial, len(tail)), 0, -1):
            if _OPEN_TAG.startswith(tail[-i:]):
                safe_end = len(self._buffer) - i
                break

        visible = self._buffer[self._sent_upto:safe_end]
        self._sent_upto = safe_end
        return visible


def describe_tool_call(name: str, arguments: Dict[str, Any]) -> str:
    args = arguments or {}

    if name == "read_file":
        return f"Read {args.get('path', '?')}"
    if name == "read_file_range":
        return f"Read {args.get('path', '?')} (lines {args.get('start_line', '?')}-{args.get('end_line', '?')})"
    if name == "list_directory":
        return f"List {args.get('path', '.')}"
    if name == "find_files":
        return f"Find files matching '{args.get('pattern', '*')}' in {args.get('directory', '.')}"
    if name == "search_code":
        return f"Search for '{args.get('query', '?')}'"
    if name == "git_status":
        return "Check git status"
    if name == "git_diff":
        path = args.get("path")
        return f"Show git diff for {path}" if path else "Show git diff"
    if name in ("write_file", "create_file"):
        return f"Write {args.get('path', '?')}"
    if name == "apply_patch":
        return f"Patch {args.get('path', '?')}"
    if name == "delete_file":
        return f"Delete {args.get('path', '?')}"
    if name == "move_file":
        return f"Move {args.get('src', '?')} -> {args.get('dst', '?')}"
    if name == "run_command":
        return f"Run: {args.get('command', '?')}"
    if name == "run_tests":
        return f"Run: {args.get('command', 'pytest -q')}"

    return f"{name}({args})"
