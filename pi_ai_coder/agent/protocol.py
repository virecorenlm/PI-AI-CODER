"""Provider-independent tool-calling protocol.

The agent loop operates entirely on these types. Whatever a given
``ModelProvider`` emits (native structured tool calls, or plain text with an
embedded ``<tool_call>{...}</tool_call>`` block) gets translated into a
``ToolCall`` before the agent ever sees it -- the loop itself never knows or
cares whether it's talking to Ollama, llama.cpp, or a fake provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolCall:
    """A single requested tool invocation."""
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """The outcome of executing a ``ToolCall``."""
    call_id: str
    tool: str
    success: bool
    output: str = ""
    error: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTurn:
    """One model turn, split into displayable prose and any requested tool calls."""
    prose: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
