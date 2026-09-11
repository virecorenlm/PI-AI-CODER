"""Shell execution tool.

Arbitrary shell command execution is EXECUTE-risk and, per CLAUDE.md, must
always originate from an explicit user action (the ``exec`` CLI command or
the TUI's "run command" action) -- never invoked automatically on the
model's say-so. A shell string genuinely needs ``shell=True`` here because
users type full shell syntax (pipes, redirects, globs); this is the one
place in the codebase that is intentional and explicit about it.
"""

from __future__ import annotations

import subprocess
import time
from typing import Iterator, Optional

from pi_ai_coder.tools.base import RiskLevel, ToolResult


class ShellTool:
    risk_level = RiskLevel.EXECUTE

    def __init__(self, cwd: Optional[str] = None, timeout: float = 30.0):
        self.cwd = cwd
        self.timeout = timeout
        self.last_result: Optional[ToolResult] = None

    def run(self, command: str) -> ToolResult:
        """Run a shell command and return the full result once it finishes."""
        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=self.timeout,
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
                duration=time.monotonic() - start,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {self.timeout:.0f}s",
                duration=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), duration=time.monotonic() - start)

    def run_streaming(self, command: str) -> Iterator[str]:
        """Run a shell command, yielding output lines as they arrive.

        After the generator is exhausted, ``self.last_result`` holds a
        ``ToolResult`` with the exit code and duration (output/error are
        left empty since callers already consumed the streamed lines).
        """
        start = time.monotonic()
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=self.cwd,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                yield line.rstrip("\n")
        finally:
            if process.stdout:
                process.stdout.close()
            process.wait()
            self.last_result = ToolResult(
                success=process.returncode == 0,
                exit_code=process.returncode,
                duration=time.monotonic() - start,
            )
