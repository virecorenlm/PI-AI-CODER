"""Tests for the bounded agent loop (AgentService) -- required tests #11-17."""

import threading
import time

import pytest

from pi_ai_coder.agent.events import AgentEventType
from pi_ai_coder.agent.service import AgentService
from pi_ai_coder.agent.tools import ToolRegistry
from pi_ai_coder.core.session import SessionState
from pi_ai_coder.models.fake_provider import FakeModelProvider
from pi_ai_coder.tools.files import FileTool
from pi_ai_coder.tools.git import GitTool
from pi_ai_coder.tools.search import SearchTool


def make_agent(tmp_path, responses, **kwargs):
    file_tool = FileTool(project_root=str(tmp_path))
    git_tool = GitTool(cwd=str(tmp_path))
    search_tool = SearchTool(project_root=str(tmp_path))
    registry = ToolRegistry(project_root=str(tmp_path), file_tool=file_tool, git_tool=git_tool, search_tool=search_tool)
    provider = FakeModelProvider(responses=responses)
    session = SessionState()
    agent = AgentService(provider=provider, tools=registry, session=session, project_root=str(tmp_path), **kwargs)
    return agent, provider, session


def tool_call_block(tool, arguments):
    import json
    return f'<tool_call>\n{json.dumps({"tool": tool, "arguments": arguments})}\n</tool_call>'


# -- 12. agent multi-step loop --------------------------------------------

def test_multi_step_loop_reads_then_patches_then_summarizes(tmp_path):
    (tmp_path / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
    responses = [
        "I'll read it first.\n" + tool_call_block("read_file", {"path": "calc.py"}),
        "Now patching.\n" + tool_call_block("apply_patch", {
            "path": "calc.py",
            "edits": [{"old": "    return a / b", "new": "    if b == 0:\n        raise ValueError('x')\n    return a / b"}],
        }),
        "Done. Added a zero-division check.",
    ]
    agent, provider, session = make_agent(tmp_path, responses)

    events = list(agent.run_task("add validation"))
    types = [e.type for e in events]

    assert AgentEventType.STARTED in types
    assert types.count(AgentEventType.TOOL_REQUESTED) == 2
    assert AgentEventType.FILE_CHANGED in types
    assert types[-1] == AgentEventType.COMPLETED
    assert "zero-division" in events[-1].data["message"]
    assert "raise ValueError" in (tmp_path / "calc.py").read_text()

    # only the user request + final prose are persisted, not raw tool JSON
    assert session.conversation == [
        {"role": "user", "content": "add validation"},
        {"role": "assistant", "content": "Done. Added a zero-division check."},
    ]


def test_no_tool_call_returns_final_response_immediately(tmp_path):
    agent, provider, session = make_agent(tmp_path, ["Sure, here's the answer: 42."])
    events = list(agent.run_task("what is the answer?"))
    assert events[-1].type == AgentEventType.COMPLETED
    assert events[-1].data["message"] == "Sure, here's the answer: 42."
    assert len([e for e in events if e.type == AgentEventType.TOOL_REQUESTED]) == 0


# -- 11. malformed tool-call rejection (loop-level retry) --------------------

def test_malformed_tool_call_is_fed_back_and_agent_can_recover(tmp_path):
    responses = [
        "<tool_call>\nnot json {{{\n</tool_call>",
        "Sorry, let me answer directly: it's fixed now.",
    ]
    agent, provider, session = make_agent(tmp_path, responses)
    events = list(agent.run_task("fix it"))
    assert events[-1].type == AgentEventType.COMPLETED
    assert events[-1].data["message"] == "Sorry, let me answer directly: it's fixed now."
    # the model must have been re-prompted with the parse error
    second_call_messages = provider.calls[1]
    assert any("invalid tool call" in m.content for m in second_call_messages)


# -- 13. max-iteration protection --------------------------------------------

def test_max_iterations_stops_cleanly(tmp_path):
    # every response requests git_status again -- never finishes
    responses = [tool_call_block("git_status", {})]
    agent, provider, session = make_agent(tmp_path, responses, max_iterations=3)
    events = list(agent.run_task("loop forever"))
    assert events[-1].type == AgentEventType.FAILED
    assert any(e.type == AgentEventType.ITERATION_LIMIT for e in events)
    assert "iteration limit" in events[-1].data["error"]
    # never persisted a bogus completion
    assert session.conversation == []


def test_max_tool_calls_stops_cleanly(tmp_path):
    responses = [tool_call_block("git_status", {})]
    agent, provider, session = make_agent(tmp_path, responses, max_iterations=100, max_tool_calls=2)
    events = list(agent.run_task("loop forever"))
    assert events[-1].type == AgentEventType.FAILED
    assert any(e.type == AgentEventType.ITERATION_LIMIT and e.data["reason"] == "max_tool_calls" for e in events)
    assert sum(1 for e in events if e.type == AgentEventType.TOOL_REQUESTED) == 2


# -- 14. cancellation --------------------------------------------------

def test_cancel_before_task_starts_stops_immediately(tmp_path):
    agent, provider, session = make_agent(tmp_path, ["irrelevant"])
    agent.cancel()  # cancelled flag set before run_task is even iterated... but run_task clears it on entry
    # so instead: cancel from a separate thread once streaming begins
    events = []
    gen = agent.run_task("do something")
    for event in gen:
        events.append(event)
        if event.type == AgentEventType.STARTED:
            agent.cancel()
    assert events[-1].type == AgentEventType.CANCELLED
    assert session.conversation == []


def test_cancel_mid_stream_via_provider_delay(tmp_path):
    file_tool = FileTool(project_root=str(tmp_path))
    git_tool = GitTool(cwd=str(tmp_path))
    search_tool = SearchTool(project_root=str(tmp_path))
    registry = ToolRegistry(project_root=str(tmp_path), file_tool=file_tool, git_tool=git_tool, search_tool=search_tool)
    provider = FakeModelProvider(response="one two three four five six seven eight", delay=0.05)
    session = SessionState()
    agent = AgentService(provider=provider, tools=registry, session=session, project_root=str(tmp_path))

    events = []

    def run():
        for event in agent.run_task("hello"):
            events.append(event)

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.12)
    agent.cancel()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert events[-1].type == AgentEventType.CANCELLED
    assert session.conversation == []


# -- 15. destructive command approval path ---------------------------------

def test_destructive_command_approved_runs(tmp_path):
    import subprocess as sp
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "--allow-empty", "-q", "-m", "init"], cwd=tmp_path, check=True)

    responses = [
        tool_call_block("run_command", {"command": "git reset --hard"}),
        "Cleaned up.",
    ]
    agent, provider, session = make_agent(tmp_path, responses, approve=lambda tc, risk: True)
    events = list(agent.run_task("reset the repo"))
    types = [e.type for e in events]
    assert AgentEventType.APPROVAL_REQUIRED in types
    finished = [e for e in events if e.type == AgentEventType.TOOL_FINISHED][0]
    assert finished.data["success"]  # approved, so it actually ran
    assert events[-1].type == AgentEventType.COMPLETED


def test_destructive_command_denied_does_not_run(tmp_path):
    marker = tmp_path / "marker.txt"
    responses = [
        tool_call_block("run_command", {"command": f"rm -rf {marker} && git reset --hard"}),
        "Understood, I won't do that.",
    ]
    marker.write_text("should survive")
    agent, provider, session = make_agent(tmp_path, responses, approve=lambda tc, risk: False)

    events = list(agent.run_task("wipe it"))
    types = [e.type for e in events]
    assert AgentEventType.APPROVAL_REQUIRED in types
    finished = [e for e in events if e.type == AgentEventType.TOOL_FINISHED][0]
    assert not finished.data["success"]
    assert marker.exists()  # never actually ran
    assert marker.read_text() == "should survive"
    assert events[-1].type == AgentEventType.COMPLETED


def test_approval_callback_receives_risk_level(tmp_path):
    from pi_ai_coder.tools.base import RiskLevel

    seen = {}

    def approve(tool_call, risk):
        seen["risk"] = risk
        return False

    responses = [tool_call_block("run_command", {"command": "git push origin main"}), "ok"]
    agent, provider, session = make_agent(tmp_path, responses, approve=approve)
    list(agent.run_task("push it"))
    assert seen["risk"] == RiskLevel.DESTRUCTIVE


def test_no_approval_needed_for_routine_command(tmp_path):
    responses = [tool_call_block("run_command", {"command": "echo hi"}), "done"]
    approve_calls = []
    agent, provider, session = make_agent(tmp_path, responses, approve=lambda tc, risk: approve_calls.append(1) or True)
    events = list(agent.run_task("say hi"))
    assert approve_calls == []  # never asked
    assert any(e.type == AgentEventType.TOOL_FINISHED and e.data["success"] for e in events)


# -- 17. file-change events -----------------------------------------------

def test_file_changed_event_fires_on_write_file(tmp_path):
    responses = [tool_call_block("write_file", {"path": "new.py", "content": "x = 1\n"}), "created it"]
    agent, provider, session = make_agent(tmp_path, responses)
    events = list(agent.run_task("create new.py"))
    file_changed = [e for e in events if e.type == AgentEventType.FILE_CHANGED]
    assert len(file_changed) == 1
    assert file_changed[0].data["tool"] == "write_file"
    assert file_changed[0].data["path"].endswith("new.py")


def test_file_changed_event_does_not_fire_on_read(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    responses = [tool_call_block("read_file", {"path": "a.py"}), "looks fine"]
    agent, provider, session = make_agent(tmp_path, responses)
    events = list(agent.run_task("check a.py"))
    assert not any(e.type == AgentEventType.FILE_CHANGED for e in events)


def test_file_changed_event_not_fired_on_failed_write(tmp_path):
    responses = [tool_call_block("apply_patch", {"path": "missing.py", "edits": [{"old": "a", "new": "b"}]}), "oops"]
    agent, provider, session = make_agent(tmp_path, responses)
    events = list(agent.run_task("patch missing file"))
    assert not any(e.type == AgentEventType.FILE_CHANGED for e in events)
    finished = [e for e in events if e.type == AgentEventType.TOOL_FINISHED][0]
    assert not finished.data["success"]
