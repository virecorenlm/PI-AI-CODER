"""Parses the text-based tool-call fallback protocol.

This is deliberately strict: only a well-formed

    <tool_call>
    {"tool": "...", "arguments": {...}}
    </tool_call>

block is treated as a tool call. Free-form prose that merely *talks about*
tools ("I'll edit auth.py now") is never executed -- only this exact,
explicit structured block is. Malformed blocks (bad JSON, missing fields,
wrong types) are reported as parse errors rather than silently ignored or
guessed at, so the agent loop can feed the error back to the model instead
of crashing or doing something unintended.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import List, Tuple

from pi_ai_coder.agent.protocol import ParsedTurn, ToolCall

_TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def parse_tool_calls(text: str) -> ParsedTurn:
    """Split ``text`` into displayable prose and any well-formed tool calls.

    Every ``<tool_call>...</tool_call>`` block is removed from the prose
    (whether it parsed successfully or not) -- the raw JSON is never shown
    to the user as if it were conversational text.
    """
    tool_calls: List[ToolCall] = []
    parse_errors: List[str] = []

    def _consume(match: "re.Match[str]") -> str:
        raw = match.group(1).strip()
        parsed, error = _parse_one(raw)
        if error:
            parse_errors.append(error)
        else:
            tool_calls.append(parsed)
        return ""

    prose = _TOOL_CALL_PATTERN.sub(_consume, text).strip()
    return ParsedTurn(prose=prose, tool_calls=tool_calls, parse_errors=parse_errors)


def _parse_one(raw_json: str) -> Tuple[ToolCall, str]:
    """Returns (ToolCall, "") on success, or (None, error_message) on failure."""
    try:
        obj = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, f"Malformed tool call JSON ({exc}): {raw_json[:200]!r}"

    if not isinstance(obj, dict):
        return None, "Tool call must be a JSON object with 'tool' and 'arguments' fields"

    name = obj.get("tool")
    if not isinstance(name, str) or not name.strip():
        return None, "Tool call is missing a valid 'tool' name"

    arguments = obj.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return None, f"Tool call '{name}': 'arguments' must be a JSON object"

    return ToolCall(id=str(uuid.uuid4()), name=name.strip(), arguments=arguments), ""
