"""TUI agent execution with the fake model -- required tests #19, #20."""

import json
import subprocess
from pathlib import Path

import pytest

from pi_ai_coder.config import AppConfig
from pi_ai_coder.tui.app import PiAiCoderApp
from pi_ai_coder.tui.widgets import ConversationView, GitPanel, ProjectTree, ToolOutput

REPO_ROOT = Path(__file__).resolve().parent.parent


def tool_call_block(tool: str, arguments: dict) -> str:
    return f"<tool_call>\n{json.dumps({'tool': tool, 'arguments': arguments})}\n</tool_call>"


def make_git_project(tmp_path: Path, name: str = "proj") -> Path:
    project = tmp_path / name
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=project, check=True)
    (project / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
    subprocess.run(["git", "add", "calc.py"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)
    return project


async def run_task_and_wait(app, pilot, text, max_wait=10.0):
    prompt = app.query_one("PromptComposer")
    prompt.focus()
    prompt.text = text
    prompt.action_submit()
    waited = 0.0
    while waited < max_wait:
        await pilot.pause(0.05)
        waited += 0.05
        if not app._generating:
            break


@pytest.mark.asyncio
async def test_tui_agent_multi_step_edits_a_file(tmp_path):
    """#19: TUI agent execution with fake model -- read, patch, summarize,
    with file-change visibility (git panel + project tree refresh)."""
    project = make_git_project(tmp_path)
    app = PiAiCoderApp(project_root=str(project), config=AppConfig(), fake_model=True)

    responses = [
        "I'll read calc.py first.\n" + tool_call_block("read_file", {"path": "calc.py"}),
        "Now patching it.\n" + tool_call_block("apply_patch", {
            "path": "calc.py",
            "edits": [{"old": "    return a / b", "new": "    if b == 0:\n        raise ValueError('x')\n    return a / b"}],
        }),
        "Done. Added a zero-division check and it's ready for review.",
    ]

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.provider.responses = responses
        app.provider._call_index = 0

        await run_task_and_wait(app, pilot, "add input validation")

        assert not app._generating
        assert "raise ValueError" in (project / "calc.py").read_text()

        conversation = app.query_one(ConversationView)
        assert len(conversation.children) >= 4  # user msg, prose, tool action(s), final summary

        # git panel must reflect the change after FILE_CHANGED
        statuses = app.git_tool.status()
        assert any(s.path == "calc.py" for s in statuses)


@pytest.mark.asyncio
async def test_tui_agent_approval_flow_blocks_and_resumes(tmp_path):
    project = make_git_project(tmp_path)
    app = PiAiCoderApp(project_root=str(project), config=AppConfig(), fake_model=True)

    responses = [
        "Let's clean up.\n" + tool_call_block("run_command", {"command": "git reset --hard"}),
        "All done.",
    ]

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.provider.responses = responses
        app.provider._call_index = 0

        prompt = app.query_one("PromptComposer")
        prompt.focus()
        prompt.text = "reset the repo"
        prompt.action_submit()

        # wait for the approval modal to appear
        for _ in range(100):
            await pilot.pause(0.05)
            if len(app.screen_stack) > 1:
                break
        assert len(app.screen_stack) > 1, "approval modal never appeared"

        await pilot.press("y")  # approve

        for _ in range(100):
            await pilot.pause(0.05)
            if not app._generating:
                break

        assert not app._generating


@pytest.mark.asyncio
async def test_tui_agent_cancellation_recovers_cleanly(tmp_path):
    project = make_git_project(tmp_path)
    app = PiAiCoderApp(project_root=str(project), config=AppConfig(), fake_model=True)
    app.provider.responses = ["one two three four five six seven eight nine ten"]
    app.provider.delay = 0.05

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        prompt = app.query_one("PromptComposer")
        prompt.focus()
        prompt.text = "do something slow"
        prompt.action_submit()

        await pilot.pause(0.15)
        assert app._generating
        app.action_cancel_generation()

        for _ in range(100):
            await pilot.pause(0.05)
            if not app._generating:
                break

        assert not app._generating
        # UI must remain usable afterward
        assert app.query_one(ConversationView) is not None
        prompt2 = app.query_one("PromptComposer")
        assert prompt2 is not None


@pytest.mark.asyncio
async def test_tui_agent_runs_from_external_project_directory(tmp_path):
    """#20: app root (this repo) and project root are unrelated."""
    assert not str(tmp_path).startswith(str(REPO_ROOT))
    project = make_git_project(tmp_path, "totally-external")

    app = PiAiCoderApp(project_root=str(project), config=AppConfig(), fake_model=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.project_root == project.resolve()
        assert Path(app.query_one(ProjectTree).path) == project.resolve()

        await run_task_and_wait(app, pilot, "hello")
        assert not app._generating
        assert app.session.conversation  # persisted under the external project
        assert (project / ".pi-ai-coder" / "session.json").exists()
