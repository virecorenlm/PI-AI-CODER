"""Structured events emitted by the agent loop.

The agent core never prints or renders anything itself -- it only yields
these events. The CLI and TUI each decide how to display them (compact
"● Read src/auth.py" action lines, streaming prose, a final summary, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class AgentEventType(Enum):
    STARTED = "agent_started"
    TOKEN = "model_token"                # a chunk of streamed assistant prose
    TOOL_REQUESTED = "tool_requested"     # model asked to run a tool
    APPROVAL_REQUIRED = "approval_required"  # a destructive tool call needs user approval
    TOOL_STARTED = "tool_started"         # tool execution began (after approval, if any)
    TOOL_FINISHED = "tool_finished"       # tool execution completed (success or failure)
    FILE_CHANGED = "file_changed"         # a tool created/modified/deleted a project file
    ITERATION_LIMIT = "iteration_limit"   # hit max iterations/tool calls
    COMPLETED = "agent_completed"         # task finished with a final message
    FAILED = "agent_failed"               # task ended due to an error
    CANCELLED = "agent_cancelled"         # task was cancelled by the user


@dataclass
class AgentEvent:
    type: AgentEventType
    data: Dict[str, Any] = field(default_factory=dict)
