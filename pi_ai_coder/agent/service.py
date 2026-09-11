"""The bounded agent loop: inspect -> edit -> test -> summarize.

This is provider-independent -- it only ever talks to ``ModelProvider``
(streamed tokens in, a full turn of text out) and to ``ToolRegistry``
(structured ``ToolCall`` in, structured ``ToolResult`` out). Whether the
underlying model is llama.cpp, Ollama, or the fake test provider is
invisible here; the same text-based ``<tool_call>`` fallback protocol
(parsed in ``pi_ai_coder.agent.parsing``) is used uniformly for all of them
so the loop never depends on native provider tool-calling.

Nothing in here prints or renders anything -- it only yields ``AgentEvent``s
for the CLI/TUI to display.
"""

from __future__ import annotations

import threading
from typing import Callable, Iterator, List, Optional

from pi_ai_coder.agent.events import AgentEvent, AgentEventType
from pi_ai_coder.agent.parsing import parse_tool_calls
from pi_ai_coder.agent.protocol import ToolCall
from pi_ai_coder.agent.protocol import ToolResult as AgentToolResult
from pi_ai_coder.agent.prompt import build_agent_system_prompt
from pi_ai_coder.agent.tools import ToolRegistry
from pi_ai_coder.core.events import EventType as ModelEventType
from pi_ai_coder.core.session import SessionState
from pi_ai_coder.models.base import Message, ModelProvider, extract_code_blocks
from pi_ai_coder.tools.base import RiskLevel

DEFAULT_MAX_ITERATIONS = 15
DEFAULT_MAX_TOOL_CALLS = 25
PERSISTED_HISTORY_TURNS = 6  # prior *persisted* conversation turns brought in for continuity

ApprovalCallback = Callable[[ToolCall, RiskLevel], bool]


def _deny_by_default(tool_call: ToolCall, risk: RiskLevel) -> bool:
    """The safe default: an AgentService built without an explicit
    ``approve`` callback never runs anything destructive."""
    return False


def _format_tool_result(result: AgentToolResult) -> str:
    header = f"Tool result for `{result.tool}` ({'success' if result.success else 'FAILED'}):"
    body = result.output if result.success and result.output else (result.error or result.output or "(no output)")
    return f"{header}\n{body}"


class AgentService:
    """Runs one bounded agent task against a project, streaming ``AgentEvent``s."""

    def __init__(
        self,
        provider: ModelProvider,
        tools: ToolRegistry,
        session: SessionState,
        project_root: str,
        approve: ApprovalCallback = _deny_by_default,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ):
        self.provider = provider
        self.tools = tools
        self.session = session
        self.project_root = project_root
        self.approve = approve
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.system_prompt = build_agent_system_prompt(tools, project_root)
        self._cancelled = threading.Event()
        self.last_code_blocks: list = []

    def cancel(self) -> None:
        """Stop the current task as soon as practical: in-flight model
        generation is cancelled immediately; a running shell command (if
        any) still runs to completion or its own timeout -- true mid-command
        preemption isn't supported without changing ShellTool's execution
        model, which this milestone reuses as-is rather than duplicating."""
        self._cancelled.set()
        self.provider.cancel()

    def run_task(self, user_message: str, hint_files: Optional[List[str]] = None) -> Iterator[AgentEvent]:
        """``hint_files`` (optional): paths the user already selected as
        relevant (e.g. via the CLI's ``add`` command) -- passed along as a
        hint so the agent reads them early, without bypassing the normal
        tool-based read flow."""
        self._cancelled.clear()
        yield AgentEvent(AgentEventType.STARTED, {"message": user_message})

        messages: List[Message] = [Message("system", self.system_prompt)]
        for turn in self.session.conversation[-PERSISTED_HISTORY_TURNS:]:
            messages.append(Message(turn["role"], turn["content"]))

        initial_content = user_message
        if hint_files:
            initial_content += "\n\n(The user has already selected these files as likely relevant -- consider reading them first: " + ", ".join(hint_files) + ")"
        messages.append(Message("user", initial_content))

        tool_call_count = 0
        final_message: Optional[str] = None

        for _iteration in range(self.max_iterations):
            if self._cancelled.is_set():
                yield AgentEvent(AgentEventType.CANCELLED, {})
                return

            collected: List[str] = []
            stream_error: Optional[str] = None
            was_cancelled = False

            for event in self.provider.stream_chat(messages):
                if event.type == ModelEventType.TOKEN:
                    collected.append(event.text)
                    yield AgentEvent(AgentEventType.TOKEN, {"text": event.text})
                elif event.type == ModelEventType.ERROR:
                    stream_error = event.text or "Model error"
                elif event.type == ModelEventType.CANCELLED:
                    was_cancelled = True

            if was_cancelled or self._cancelled.is_set():
                yield AgentEvent(AgentEventType.CANCELLED, {})
                return
            if stream_error:
                yield AgentEvent(AgentEventType.FAILED, {"error": stream_error})
                return

            full_text = "".join(collected)
            parsed = parse_tool_calls(full_text)
            messages.append(Message("assistant", full_text))

            if not parsed.tool_calls:
                if parsed.parse_errors:
                    error_text = "; ".join(parsed.parse_errors)
                    messages.append(Message(
                        "user",
                        f"Your last response had an invalid tool call and was not executed: {error_text}\n"
                        "Respond again with either one well-formed <tool_call> block, or plain prose if no tool is needed.",
                    ))
                    continue
                final_message = parsed.prose
                break

            tool_call = parsed.tool_calls[0]
            if len(parsed.tool_calls) > 1 or parsed.parse_errors:
                note_parts = []
                if len(parsed.tool_calls) > 1:
                    note_parts.append("only the first tool call in that response was processed")
                if parsed.parse_errors:
                    note_parts.append("; ".join(parsed.parse_errors))
                messages.append(Message("user", "Note: " + "; ".join(note_parts)))

            if tool_call_count >= self.max_tool_calls:
                yield AgentEvent(AgentEventType.ITERATION_LIMIT, {"reason": "max_tool_calls", "limit": self.max_tool_calls})
                yield AgentEvent(AgentEventType.FAILED, {"error": f"Stopped after reaching the tool-call limit ({self.max_tool_calls})."})
                return
            tool_call_count += 1

            yield AgentEvent(AgentEventType.TOOL_REQUESTED, {"tool": tool_call.name, "arguments": tool_call.arguments, "id": tool_call.id})

            risk = self.tools.classify(tool_call)
            if risk == RiskLevel.DESTRUCTIVE:
                yield AgentEvent(AgentEventType.APPROVAL_REQUIRED, {"tool": tool_call.name, "arguments": tool_call.arguments})
                if self._cancelled.is_set():
                    yield AgentEvent(AgentEventType.CANCELLED, {})
                    return
                approved = self.approve(tool_call, risk)
                if not approved:
                    result = AgentToolResult(
                        call_id=tool_call.id, tool=tool_call.name, success=False,
                        error="Rejected by the user. Do not repeat this exact command -- try a different, non-destructive approach or ask the user for guidance.",
                    )
                    yield AgentEvent(AgentEventType.TOOL_FINISHED, {"tool": tool_call.name, "success": False, "approved": False})
                    messages.append(Message("user", _format_tool_result(result)))
                    continue
                yield AgentEvent(AgentEventType.TOOL_STARTED, {"tool": tool_call.name})
                result = self.tools.execute(tool_call)
            else:
                yield AgentEvent(AgentEventType.TOOL_STARTED, {"tool": tool_call.name})
                result = self.tools.execute(tool_call)

            spec = self.tools.get(tool_call.name)
            if result.success and spec is not None and spec.changes_files:
                path = result.data.get("path") or result.data.get("old_path")
                yield AgentEvent(AgentEventType.FILE_CHANGED, {"tool": tool_call.name, "path": path, "diff": result.data.get("diff")})

            yield AgentEvent(AgentEventType.TOOL_FINISHED, {
                "tool": tool_call.name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
            })

            messages.append(Message("user", _format_tool_result(result)))
        else:
            yield AgentEvent(AgentEventType.ITERATION_LIMIT, {"reason": "max_iterations", "limit": self.max_iterations})
            yield AgentEvent(AgentEventType.FAILED, {"error": f"Stopped after reaching the iteration limit ({self.max_iterations}) without finishing."})
            return

        # Persist only the user's request and the final prose summary -- not
        # the raw tool-call/result exchange -- so conversation history
        # restored across restarts stays clean (CLAUDE.md: don't flood the
        # conversation with raw internal reasoning).
        self.session.add_turn("user", user_message)
        self.session.add_turn("assistant", final_message or "(no response)")
        self.session.add_prompt(user_message)
        self.last_code_blocks = extract_code_blocks(final_message or "")
        yield AgentEvent(AgentEventType.COMPLETED, {"message": final_message or ""})
