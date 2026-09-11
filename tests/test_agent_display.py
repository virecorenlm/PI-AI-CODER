"""Tests for shared agent-action display formatting."""

import random

from pi_ai_coder.agent.display import LiveProseFilter, describe_tool_call


def test_describe_read_file():
    assert describe_tool_call("read_file", {"path": "a.py"}) == "Read a.py"


def test_describe_apply_patch():
    assert describe_tool_call("apply_patch", {"path": "a.py", "edits": []}) == "Patch a.py"


def test_describe_run_command_shows_actual_command():
    assert describe_tool_call("run_command", {"command": "pytest -q"}) == "Run: pytest -q"


def test_describe_run_tests_defaults_to_pytest_when_no_command_given():
    """Regression: previously showed "Run: ?" when the model called
    run_tests with no arguments (it defaults to `pytest -q` internally)."""
    assert describe_tool_call("run_tests", {}) == "Run: pytest -q"
    assert describe_tool_call("run_tests", {"command": "npm test"}) == "Run: npm test"


def test_describe_unknown_tool_falls_back_to_generic_form():
    result = describe_tool_call("mystery_tool", {"x": 1})
    assert "mystery_tool" in result


def test_live_prose_filter_hides_tool_call_json_regardless_of_chunk_boundaries():
    text = 'Prose before.\n<tool_call>\n{"tool": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>'
    rng = random.Random(42)
    f = LiveProseFilter()
    visible = ""
    i = 0
    while i < len(text):
        n = rng.randint(1, 5)
        visible += f.feed(text[i:i + n])
        i += n
    assert visible == "Prose before.\n"
    assert "tool_call" not in visible
    assert "read_file" not in visible


def test_live_prose_filter_passes_through_plain_prose_untouched():
    text = "No tool call here, just an answer."
    f = LiveProseFilter()
    assert f.feed(text) == text
