"""Event types used to stream model/tool activity to a UI.

Both the CLI and the Textual TUI consume the same event stream from
``AssistantService``/``ModelProvider`` so neither has to know how inference
or tool execution actually happens.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class EventType(Enum):
    STATUS = "status"          # assistant lifecycle status changed
    TOKEN = "token"             # a chunk of generated text
    TOOL_START = "tool_start"   # a tool began executing
    TOOL_OUTPUT = "tool_output"  # incremental tool output
    TOOL_END = "tool_end"       # a tool finished
    ERROR = "error"             # a recoverable/reportable error
    DONE = "done"                # generation finished successfully
    CANCELLED = "cancelled"      # generation was cancelled by the user


class AssistantStatus(Enum):
    IDLE = "idle"
    BUILDING_CONTEXT = "building_context"
    GENERATING = "generating"
    RUNNING_TOOL = "running_tool"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: EventType
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
