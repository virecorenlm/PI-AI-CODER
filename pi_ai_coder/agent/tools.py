"""Wires the agent's tool set on top of the existing FileTool/GitTool/
ShellTool/SearchTool services -- no file, shell, or git logic is
reimplemented here, only argument validation, output capping, and dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pi_ai_coder.agent.permissions import TOOL_RISK, classify_command
from pi_ai_coder.agent.protocol import ToolCall
from pi_ai_coder.agent.protocol import ToolResult as AgentToolResult
from pi_ai_coder.tools.base import PathOutsideProjectError, RiskLevel, resolve_within_project
from pi_ai_coder.tools.files import FileTool
from pi_ai_coder.tools.git import GitTool
from pi_ai_coder.tools.search import SearchTool
from pi_ai_coder.tools.shell import ShellTool
from pi_ai_coder.tools.base import ToolResult as RawToolResult

DEFAULT_COMMAND_TIMEOUT = 60.0
DEFAULT_MAX_OUTPUT_CHARS = 6000


class ToolArgumentError(ValueError):
    """Raised by argument validation helpers; caught by ToolRegistry.execute
    and turned into a clean failed ToolResult instead of crashing the loop."""


def _require_str(args: Dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise ToolArgumentError(f"argument '{key}' is required and must be a non-empty string")
    return value


def _optional_str(args: Dict[str, Any], key: str, default: Optional[str] = None) -> Optional[str]:
    value = args.get(key, default)
    if value is not None and not isinstance(value, str):
        raise ToolArgumentError(f"argument '{key}' must be a string")
    return value


def _optional_int(args: Dict[str, Any], key: str, default: int) -> int:
    value = args.get(key, default)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolArgumentError(f"argument '{key}' must be an integer")


def _require_list(args: Dict[str, Any], key: str) -> list:
    value = args.get(key)
    if not isinstance(value, list):
        raise ToolArgumentError(f"argument '{key}' must be a list")
    return value


def truncate(text: str, max_chars: int) -> tuple:
    if text is None or len(text) <= max_chars:
        return text or "", False
    return text[:max_chars] + f"\n... [truncated, {len(text) - max_chars} more characters]", True


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[[Dict[str, Any]], RawToolResult]
    changes_files: bool = False


class ToolRegistry:
    """The agent's callable tool set, bound to one project."""

    def __init__(
        self,
        project_root: str,
        file_tool: FileTool,
        git_tool: GitTool,
        search_tool: SearchTool,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ):
        self.project_root = project_root
        self.file_tool = file_tool
        self.git_tool = git_tool
        self.search_tool = search_tool
        self.command_timeout = command_timeout
        self.max_output_chars = max_output_chars
        self._specs: Dict[str, ToolSpec] = {}
        self._register_all()

    # -- registration ---------------------------------------------------

    def _reg(self, name: str, description: str, handler: Callable[[Dict[str, Any]], RawToolResult], changes_files: bool = False) -> None:
        self._specs[name] = ToolSpec(name=name, description=description, handler=handler, changes_files=changes_files)

    def _register_all(self) -> None:
        self._reg(
            "read_file",
            'read_file(path: str) -> full contents of a text file.',
            lambda a: self.file_tool.read_text(_require_str(a, "path")),
        )
        self._reg(
            "read_file_range",
            'read_file_range(path: str, start_line: int, end_line: int) -> a slice of a file (1-indexed, inclusive). Use for large files instead of read_file.',
            lambda a: self.file_tool.read_file_range(_require_str(a, "path"), _optional_int(a, "start_line", 1), _optional_int(a, "end_line", 200)),
        )
        self._reg(
            "list_directory",
            'list_directory(path: str = ".") -> immediate entries (files and dirs) of a directory.',
            lambda a: self.file_tool.list_directory(_optional_str(a, "path", ".")),
        )
        self._reg(
            "find_files",
            'find_files(pattern: str = "*", directory: str = ".", max_results: int = 100) -> file paths matching a glob pattern (e.g. "*.py").',
            lambda a: self.file_tool.find_files(_optional_str(a, "pattern", "*"), _optional_str(a, "directory", "."), _optional_int(a, "max_results", 100)),
        )
        self._reg(
            "search_code",
            'search_code(query: str, glob: str = null, directory: str = ".", max_results: int = 50) -> "path:line:text" matches for a text/regex query across the project.',
            self._search_code,
        )
        self._reg(
            "git_status",
            "git_status() -> current branch and working-tree status (modified/untracked/staged files).",
            self._git_status,
        )
        self._reg(
            "git_diff",
            "git_diff(path: str = null) -> unstaged diff for the whole project or one file.",
            self._git_diff,
        )
        self._reg(
            "write_file",
            "write_file(path: str, content: str) -> create a file or fully overwrite an existing one. Prefer apply_patch for small edits to existing files.",
            lambda a: self.file_tool.save(_require_str(a, "path"), _optional_str(a, "content", "") or ""),
            changes_files=True,
        )
        self._reg(
            "create_file",
            "create_file(path: str, content: str = \"\") -> create a brand-new file. Fails if the file already exists.",
            lambda a: self.file_tool.create_file(_require_str(a, "path"), _optional_str(a, "content", "") or ""),
            changes_files=True,
        )
        self._reg(
            "apply_patch",
            'apply_patch(path: str, edits: [{"old": str, "new": str}]) -> apply one or more exact-match search/replace edits to an existing file. Each "old" must match exactly once in the current file. Preferred way to make small, targeted edits.',
            self._apply_patch,
            changes_files=True,
        )
        self._reg(
            "delete_file",
            "delete_file(path: str) -> delete a single file (not directories).",
            lambda a: self.file_tool.delete_file(_require_str(a, "path")),
            changes_files=True,
        )
        self._reg(
            "move_file",
            "move_file(src: str, dst: str) -> rename/move a file within the project.",
            lambda a: self.file_tool.move_file(_require_str(a, "src"), _require_str(a, "dst")),
            changes_files=True,
        )
        self._reg(
            "run_command",
            'run_command(command: str, cwd: str = null, timeout: number = null) -> run a shell command (e.g. tests, linters, build tools) and return stdout/stderr/exit code. Obviously destructive commands require user approval.',
            self._run_command,
        )
        self._reg(
            "run_tests",
            'run_tests(command: str = "pytest -q") -> convenience wrapper around run_command defaulting to the project\'s test command.',
            self._run_tests,
        )

    # -- handlers needing extra context/validation --------------------------

    def _search_code(self, args: Dict[str, Any]) -> RawToolResult:
        query = _require_str(args, "query")
        glob = _optional_str(args, "glob")
        directory = _optional_str(args, "directory", ".")
        max_results = _optional_int(args, "max_results", 50)
        result = self.search_tool.search(query, glob=glob, directory=directory, max_results=max_results)
        output, _ = truncate(result.output, self.max_output_chars)
        return RawToolResult(success=result.success, output=output, error=result.error, data=result.data)

    def _git_status(self, args: Dict[str, Any]) -> RawToolResult:
        if not self.git_tool.is_repo():
            return RawToolResult(success=True, output="Not a git repository.")
        branch = self.git_tool.current_branch()
        statuses = self.git_tool.status()
        lines = [f"branch: {branch or '(detached)'}"]
        if not statuses:
            lines.append("(clean)")
        else:
            for s in statuses:
                lines.append(f"{s.describe():24} {s.path}")
        return RawToolResult(success=True, output="\n".join(lines))

    def _git_diff(self, args: Dict[str, Any]) -> RawToolResult:
        if not self.git_tool.is_repo():
            return RawToolResult(success=True, output="Not a git repository.")
        path = _optional_str(args, "path")
        result = self.git_tool.diff(path=path)
        output = result.output if result.output else "No changes"
        output, _ = truncate(output, self.max_output_chars)
        return RawToolResult(success=result.success, output=output, error=result.error)

    def _apply_patch(self, args: Dict[str, Any]) -> RawToolResult:
        path = _require_str(args, "path")
        edits = _require_list(args, "edits")
        return self.file_tool.apply_patch(path, edits)

    def _run_command(self, args: Dict[str, Any]) -> RawToolResult:
        command = _require_str(args, "command")
        cwd_arg = _optional_str(args, "cwd")
        if cwd_arg:
            try:
                resolved_cwd = resolve_within_project(cwd_arg, self.project_root)
            except PathOutsideProjectError as exc:
                return RawToolResult(success=False, error=str(exc))
            if not resolved_cwd.is_dir():
                return RawToolResult(success=False, error=f"Not a directory: {cwd_arg}")
            effective_cwd = str(resolved_cwd)
        else:
            effective_cwd = self.project_root

        requested_timeout = args.get("timeout")
        timeout = self.command_timeout
        if requested_timeout is not None:
            try:
                timeout = min(float(requested_timeout), self.command_timeout)
            except (TypeError, ValueError):
                raise ToolArgumentError("argument 'timeout' must be a number")

        shell = ShellTool(cwd=effective_cwd, timeout=timeout)
        result = shell.run(command)

        output, out_truncated = truncate(result.output, self.max_output_chars)
        error, err_truncated = truncate(result.error, self.max_output_chars)
        combined = output
        if error:
            combined += f"\n--- stderr ---\n{error}"
        if out_truncated or err_truncated:
            combined += "\n[output truncated]"

        return RawToolResult(
            success=result.success,
            output=combined,
            error="" if result.success else (result.error or f"exit code {result.exit_code}"),
            data={"exit_code": result.exit_code, "duration": result.duration, "command": command, "cwd": effective_cwd},
        )

    def _run_tests(self, args: Dict[str, Any]) -> RawToolResult:
        merged = dict(args)
        merged.setdefault("command", "pytest -q")
        return self._run_command(merged)

    # -- registry API used by the agent loop ---------------------------------

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._specs.get(name)

    def all(self) -> List[ToolSpec]:
        return list(self._specs.values())

    def classify(self, tool_call: ToolCall) -> Optional[RiskLevel]:
        """Returns None for an unknown tool name (the loop handles that as a plain error)."""
        if tool_call.name in ("run_command", "run_tests"):
            command = tool_call.arguments.get("command", "") if isinstance(tool_call.arguments, dict) else ""
            return classify_command(command)
        if tool_call.name not in self._specs:
            return None
        return TOOL_RISK.get(tool_call.name, RiskLevel.WRITE)

    def execute(self, tool_call: ToolCall) -> AgentToolResult:
        spec = self.get(tool_call.name)
        if spec is None:
            return AgentToolResult(
                call_id=tool_call.id,
                tool=tool_call.name,
                success=False,
                error=f"Unknown tool '{tool_call.name}'. Available tools: {', '.join(sorted(self._specs))}",
            )
        try:
            raw = spec.handler(tool_call.arguments or {})
        except ToolArgumentError as exc:
            return AgentToolResult(call_id=tool_call.id, tool=tool_call.name, success=False, error=str(exc))
        except Exception as exc:  # never let a tool crash the whole agent loop
            return AgentToolResult(call_id=tool_call.id, tool=tool_call.name, success=False, error=f"Tool '{tool_call.name}' raised an error: {exc}")

        return AgentToolResult(
            call_id=tool_call.id,
            tool=tool_call.name,
            success=raw.success,
            output=raw.output,
            error=raw.error,
            data=raw.data,
        )
