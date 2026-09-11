"""Smoke tests for the Textual TUI, using the fake model backend so no
llama.cpp build or GGUF file is required. Runs headless via Textual's
Pilot test harness."""

import asyncio

import pytest

from pi_ai_coder.config import AppConfig
from pi_ai_coder.tui.app import PiAiCoderApp
from pi_ai_coder.tui.widgets import ConversationView, ContextPanel, ProjectTree, PromptComposer, ToolOutput


@pytest.fixture
def app(tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    pass\n")
    (tmp_path / "README.md").write_text("# demo\n")
    return PiAiCoderApp(project_root=str(tmp_path), config=AppConfig(), fake_model=True)


@pytest.mark.asyncio
async def test_app_boots_and_shows_widgets(app):
    async with app.run_test() as pilot:
        assert app.query_one(ProjectTree)
        assert app.query_one(ConversationView)
        assert app.query_one(PromptComposer)


@pytest.mark.asyncio
async def test_submitting_a_prompt_streams_a_response(app):
    async with app.run_test() as pilot:
        prompt = app.query_one(PromptComposer)
        prompt.focus()
        prompt.text = "hello there"
        prompt.action_submit()

        for _ in range(50):
            await pilot.pause(0.05)
            if not app._generating:
                break

        assert not app._generating
        conversation = app.query_one(ConversationView)
        assert len(conversation.children) >= 2  # user message + assistant message
        assert len(app.session.conversation) == 2


@pytest.mark.asyncio
async def test_add_and_remove_context_file(app, tmp_path):
    async with app.run_test() as pilot:
        path = str(tmp_path / "main.py")
        app.request_context_toggle(path, True)
        assert path in app.session.context_files

        app.request_context_toggle(path, False)
        assert path not in app.session.context_files


@pytest.mark.asyncio
async def test_reset_conversation_clears_state(app):
    async with app.run_test() as pilot:
        prompt = app.query_one(PromptComposer)
        prompt.focus()
        prompt.text = "hi"
        prompt.action_submit()

        for _ in range(50):
            await pilot.pause(0.05)
            if not app._generating:
                break

        app.action_reset_conversation()
        assert app.session.conversation == []


@pytest.mark.asyncio
async def test_list_models_writes_to_tool_output(app):
    async with app.run_test() as pilot:
        app._cmd_list_models()
        await pilot.pause()
        tool_output = app.query_one(ToolOutput)
        rendered = "\n".join(strip.text for strip in tool_output.lines)
        assert "fake-model-v1" in rendered
        assert "fake-model-v2" in rendered


@pytest.mark.asyncio
async def test_change_model_switches_provider_model(app):
    async with app.run_test() as pilot:
        app._on_change_model_entered("fake-model-v2")
        assert app.provider.info().model_name == "fake-model-v2"


@pytest.mark.asyncio
async def test_health_check_warning_shown_for_unavailable_provider(tmp_path):
    from pi_ai_coder.config import AppConfig

    config = AppConfig()
    config.model.provider = "ollama"
    config.ollama.host = "http://127.0.0.1:1"  # nothing listens here
    config.ollama.model = "does-not-matter"
    app = PiAiCoderApp(project_root=str(tmp_path), config=config, fake_model=False)

    async with app.run_test() as pilot:
        for _ in range(40):
            await pilot.pause(0.1)
            conversation = app.query_one(ConversationView)
            if len(conversation.children) > 0:
                break
        conversation = app.query_one(ConversationView)
        assert len(conversation.children) > 0
