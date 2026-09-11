"""Tests for the text-based tool-call parsing protocol (required test #10, #11)."""

from pi_ai_coder.agent.parsing import parse_tool_calls


def test_parses_well_formed_tool_call():
    text = '<tool_call>\n{"tool": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>'
    parsed = parse_tool_calls(text)
    assert parsed.prose == ""
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "read_file"
    assert parsed.tool_calls[0].arguments == {"path": "a.py"}
    assert parsed.parse_errors == []


def test_prose_before_tool_call_is_preserved():
    text = 'I will inspect this file.\n<tool_call>\n{"tool": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>'
    parsed = parse_tool_calls(text)
    assert parsed.prose == "I will inspect this file."
    assert len(parsed.tool_calls) == 1


def test_plain_prose_with_no_tool_call():
    text = "Just a plain answer, no tool needed."
    parsed = parse_tool_calls(text)
    assert parsed.prose == text
    assert parsed.tool_calls == []
    assert parsed.parse_errors == []


def test_tool_call_missing_arguments_defaults_to_empty_dict():
    text = '<tool_call>\n{"tool": "git_status"}\n</tool_call>'
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls[0].arguments == {}


def test_prose_talking_about_tools_is_not_executed():
    """"I think I'll edit auth.py now" must never be treated as a tool call."""
    text = "I think I'll edit auth.py now."
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls == []
    assert parsed.prose == text


def test_malformed_json_is_rejected_not_crashed():
    text = "<tool_call>\nnot valid json at all {{{\n</tool_call>"
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls == []
    assert len(parsed.parse_errors) == 1
    assert "Malformed" in parsed.parse_errors[0]
    # the malformed block must not leak into displayed prose
    assert "not valid json" not in parsed.prose


def test_tool_call_missing_tool_field_is_rejected():
    text = '<tool_call>\n{"arguments": {"path": "a.py"}}\n</tool_call>'
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls == []
    assert len(parsed.parse_errors) == 1


def test_tool_call_with_non_object_arguments_is_rejected():
    text = '<tool_call>\n{"tool": "read_file", "arguments": "a.py"}\n</tool_call>'
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls == []
    assert len(parsed.parse_errors) == 1


def test_tool_call_that_is_not_a_json_object_is_rejected():
    text = "<tool_call>\n[1, 2, 3]\n</tool_call>"
    parsed = parse_tool_calls(text)
    assert parsed.tool_calls == []
    assert len(parsed.parse_errors) == 1


def test_multiple_tool_calls_in_one_response_all_parsed():
    text = (
        '<tool_call>\n{"tool": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>\n'
        '<tool_call>\n{"tool": "read_file", "arguments": {"path": "b.py"}}\n</tool_call>'
    )
    parsed = parse_tool_calls(text)
    assert len(parsed.tool_calls) == 2
    assert [c.name for c in parsed.tool_calls] == ["read_file", "read_file"]


def test_each_tool_call_gets_a_unique_id():
    text = (
        '<tool_call>\n{"tool": "git_status"}\n</tool_call>\n'
        '<tool_call>\n{"tool": "git_status"}\n</tool_call>'
    )
    parsed = parse_tool_calls(text)
    ids = {c.id for c in parsed.tool_calls}
    assert len(ids) == 2
