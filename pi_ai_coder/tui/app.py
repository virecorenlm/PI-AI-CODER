"""The Textual TUI application.

This module only wires widgets to the ``pi_ai_coder`` service layer -- it
contains no model, git, or shell implementation of its own. All of that
lives in ``pi_ai_coder.core``/``models``/``tools``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from textual import work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer

from pi_ai_coder.config import AppConfig, load_config
from pi_ai_coder.context.manager import ContextManager
from pi_ai_coder.core.assistant_service import AssistantService
from pi_ai_coder.core.events import AssistantStatus, EventType, StreamEvent
from pi_ai_coder.core.session import SessionStore
from pi_ai_coder.models.factory import create_provider
from pi_ai_coder.tools.files import FileTool
from pi_ai_coder.tools.git import GitTool
from pi_ai_coder.tools.shell import ShellTool
from pi_ai_coder.tui.screens import CommandInputScreen, HelpScreen, PreviewScreen
from pi_ai_coder.tui.widgets import (
    ContextPanel,
    ConversationView,
    GitPanel,
    ProjectTree,
    PromptComposer,
    PromptSubmitted,
    StatusBar,
    ToolOutput,
)

APP_CSS = """
Screen {
    layout: vertical;
}

#status-bar {
    height: 1;
    background: $panel;
    padding: 0 1;
}

#main-body {
    height: 1fr;
}

#left-column {
    width: 32;
    min-width: 24;
}

#project-tree {
    height: 2fr;
    border: solid $primary-background;
}

#context-panel {
    height: 1fr;
    min-height: 6;
    border: solid $primary-background;
    padding: 0 1;
}

#right-column {
    width: 1fr;
}

#conversation {
    height: 1fr;
    border: solid $primary-background;
    padding: 0 1;
}

#prompt {
    height: 6;
    border: solid $accent;
}

#bottom-panels {
    height: 10;
}

#git-panel {
    width: 32;
    min-width: 24;
    border: solid $primary-background;
    padding: 0 1;
}

#tool-output {
    width: 1fr;
    border: solid $primary-background;
}

.message {
    margin: 0 0 1 0;
}

.error-message {
    margin: 0 0 1 0;
}

#command-input-dialog {
    align: center middle;
    width: 60%;
    height: auto;
    background: $panel;
    border: solid $accent;
    padding: 1 2;
}
"""


class PiAiCoderApp(App):
    """PI-AI-CODER Textual workspace."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+o", "focus_tree", "Files"),
        Binding("ctrl+l", "focus_prompt", "Prompt"),
        Binding("ctrl+g", "focus_git", "Git"),
        Binding("ctrl+t", "focus_tool_output", "Tools"),
        Binding("ctrl+r", "reset_conversation", "Reset"),
        Binding("ctrl+k", "clear_context", "Clear ctx"),
        Binding("f1", "show_help", "Help"),
        Binding("ctrl+c", "cancel_generation", "Cancel", show=False),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, project_root: str, config: AppConfig, fake_model: bool = False):
        super().__init__()
        self.project_root = Path(project_root).resolve()
        self.config = config
        self.fake_model = fake_model
        self._generating = False

        self.context_manager = ContextManager(max_file_size_kb=config.project.max_file_size_kb)
        self.session_store = SessionStore(project_root=str(self.project_root))
        had_existing_session = self.session_store.state_file.exists()
        self.session = self.session_store.load()
        if not had_existing_session:
            self.session.auto_context = config.project.auto_context

        self.provider = create_provider(config, fake_model=fake_model)

        self.service = AssistantService(
            provider=self.provider,
            context_manager=self.context_manager,
            session=self.session,
            project_root=str(self.project_root),
        )

        self.shell_tool = ShellTool(cwd=str(self.project_root))
        self.git_tool = GitTool(cwd=str(self.project_root))
        self.file_tool = FileTool(project_root=str(self.project_root))

    # -- layout --------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="main-body"):
            with Vertical(id="left-column"):
                yield ProjectTree(str(self.project_root), self.context_manager, id="project-tree")
                yield ContextPanel(id="context-panel")
            with Vertical(id="right-column"):
                yield ConversationView(id="conversation")
                yield PromptComposer(id="prompt")
        with Horizontal(id="bottom-panels"):
            yield GitPanel(id="git-panel")
            yield ToolOutput(id="tool-output")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "PI-AI-CODER"

        prompt = self.query_one(PromptComposer)
        prompt.set_history(list(self.session.recent_prompts))

        conversation = self.query_one(ConversationView)
        for turn in self.session.conversation[-10:]:
            if turn["role"] == "user":
                conversation.add_user_message(turn["content"])
            else:
                conversation.start_assistant_message()
                conversation.append_assistant_token(turn["content"])
                conversation.finish_assistant_message()

        self._refresh_status_bar("idle")
        self._refresh_context_panel()
        self._refresh_git_panel()

        gitignore_updated = self.session_store.ensure_gitignored()
        if gitignore_updated:
            conversation.add_system_message(
                f"Added {self.session_store.state_dir.name}/ to .gitignore so session state stays local."
            )

        prompt.focus()

        if not self.fake_model:
            self._check_provider_health()

    @work(thread=True, group="health-check")
    def _check_provider_health(self) -> None:
        health = self.provider.health_check()
        if not health.available:
            self.call_from_thread(self.query_one(ConversationView).add_system_message, health.message)

    # -- status / panel refresh -----------------------------------------

    def _refresh_status_bar(self, status_text: str) -> None:
        info = self.provider.info()
        self.query_one(StatusBar).update_status(
            project_name=str(self.project_root),
            model_name=f"{info.model_name} ({info.name})",
            status_text=status_text,
        )

    def _refresh_context_panel(self, auto_discovered: Optional[List[str]] = None, context_chars: int = 0) -> None:
        self.query_one(ContextPanel).update_context(
            context_files=self.session.context_files,
            auto_context=self.session.auto_context,
            auto_discovered_files=auto_discovered,
            context_chars=context_chars,
        )
        self.query_one(ProjectTree).set_context_files(self.session.context_files)

    def _refresh_git_panel(self) -> None:
        is_repo = self.git_tool.is_repo()
        branch = self.git_tool.current_branch() if is_repo else None
        statuses = self.git_tool.status() if is_repo else []
        self.query_one(GitPanel).update_status(branch, statuses, is_repo=is_repo)

    def _save_session(self) -> None:
        self.session_store.save(self.session)

    # -- prompt submit / generation --------------------------------------

    def on_prompt_submitted(self, message: PromptSubmitted) -> None:
        if self._generating:
            self.bell()
            return

        text = message.text
        self.query_one(ConversationView).add_user_message(text)
        self._generating = True
        self._refresh_status_bar("generating...")
        self._run_generation(text)

    @work(thread=True, exclusive=True, group="generation")
    def _run_generation(self, prompt: str) -> None:
        for event in self.service.stream_chat(prompt):
            self.call_from_thread(self._handle_stream_event, event)
        self.call_from_thread(self._on_generation_finished)

    def _handle_stream_event(self, event: StreamEvent) -> None:
        conversation = self.query_one(ConversationView)

        if event.type == EventType.STATUS:
            status = event.data.get("status")
            if status == AssistantStatus.BUILDING_CONTEXT:
                self._refresh_status_bar("building context...")
                if "files" in event.data:
                    auto_discovered = event.data["files"] if event.data.get("auto_discovered") else None
                    self._refresh_context_panel(
                        auto_discovered=auto_discovered,
                        context_chars=event.data.get("context_chars", 0),
                    )
            elif status == AssistantStatus.GENERATING:
                conversation.start_assistant_message()
                self._refresh_status_bar("generating...")
        elif event.type == EventType.TOKEN:
            conversation.append_assistant_token(event.text)
        elif event.type == EventType.ERROR:
            conversation.finish_assistant_message()
            conversation.add_error(event.text or "Unknown model error")
        elif event.type == EventType.CANCELLED:
            conversation.finish_assistant_message()
            conversation.add_system_message("Generation cancelled")

    def _on_generation_finished(self) -> None:
        self.query_one(ConversationView).finish_assistant_message()
        self._generating = False
        self._refresh_status_bar("idle")
        self._save_session()

    def action_cancel_generation(self) -> None:
        if self._generating:
            self.service.cancel()

    # -- context file management -----------------------------------------

    def request_context_toggle(self, path: str, add: bool) -> None:
        if add:
            self.service.add_context_files([path])
        else:
            self.service.remove_context_files(path)
        self._refresh_context_panel()
        self._save_session()

    def on_project_tree_context_toggle_requested(self, message: ProjectTree.ContextToggleRequested) -> None:
        self.request_context_toggle(message.path, message.add)

    def on_directory_tree_file_selected(self, message) -> None:
        path = str(message.path)
        result = self.file_tool.read_text(path)
        if not result.success:
            self.query_one(ConversationView).add_error(result.error)
            return
        resolved_context = {str(Path(p).resolve()) for p in self.session.context_files}
        in_context = str(Path(path).resolve()) in resolved_context
        self.push_screen(PreviewScreen(path, result.output, in_context))

    # -- key bindings ------------------------------------------------------

    def action_focus_tree(self) -> None:
        self.query_one(ProjectTree).focus()

    def action_focus_prompt(self) -> None:
        self.query_one(PromptComposer).focus()

    def action_focus_git(self) -> None:
        self._refresh_git_panel()
        self.query_one(GitPanel).focus()

    def action_focus_tool_output(self) -> None:
        self.query_one(ToolOutput).focus()

    def action_reset_conversation(self) -> None:
        self.service.reset()
        self.query_one(ConversationView).clear_conversation()
        self._save_session()

    def action_clear_context(self) -> None:
        self.service.clear_context_files()
        self._refresh_context_panel()
        self._save_session()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_refresh_project(self) -> None:
        self.query_one(ProjectTree).reload()
        self._refresh_git_panel()
        self.context_manager.invalidate()

    # -- shell execution ---------------------------------------------------

    def run_shell_command(self, command: str) -> None:
        if not command.strip():
            return
        tool_output = self.query_one(ToolOutput)
        tool_output.command_header(command)
        self._run_shell(command)

    @work(thread=True, exclusive=True, group="shell")
    def _run_shell(self, command: str) -> None:
        tool_output = self.query_one(ToolOutput)
        for line in self.shell_tool.run_streaming(command):
            self.call_from_thread(tool_output.line, line)
        result = self.shell_tool.last_result
        self.call_from_thread(
            tool_output.command_footer,
            result.exit_code if result else None,
            result.duration if result else None,
        )
        self.call_from_thread(self._refresh_git_panel)

    def _prompt_for_shell_command(self) -> None:
        self.push_screen(
            CommandInputScreen("Run shell command:", placeholder="pytest -q"),
            callback=self._on_shell_command_entered,
        )

    def _on_shell_command_entered(self, command: Optional[str]) -> None:
        if command:
            self.run_shell_command(command)

    # -- git diff ------------------------------------------------------

    def action_show_git_diff(self) -> None:
        tool_output = self.query_one(ToolOutput)
        if not self.git_tool.is_repo():
            tool_output.line("[dim]Not a git repository[/dim]")
            return
        result = self.git_tool.diff()
        tool_output.command_header("git diff")
        if result.output:
            for line in result.output.splitlines():
                tool_output.line(line)
        else:
            tool_output.line("[dim]No changes[/dim]")
        tool_output.command_footer(result.exit_code, None)

    # -- command palette additions -----------------------------------------

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("Add file to context", "Add the file selected in the tree", self._cmd_add_selected_to_context)
        yield SystemCommand("Remove file from context", "Remove the file selected in the tree", self._cmd_remove_selected_from_context)
        yield SystemCommand("Clear context", "Clear all manually selected context files", self.action_clear_context)
        yield SystemCommand("Toggle auto context", "Toggle automatic context file discovery", self._cmd_toggle_auto_context)
        yield SystemCommand("Reset conversation", "Clear the conversation history", self.action_reset_conversation)
        yield SystemCommand("Show git diff", "Show `git diff` in the tool output pane", self.action_show_git_diff)
        yield SystemCommand("Run shell command", "Run a shell command and show its output", self._prompt_for_shell_command)
        yield SystemCommand("Refresh project", "Reload the file tree and git status", self.action_refresh_project)
        yield SystemCommand("List models", "List models available for the current provider", self._cmd_list_models)
        yield SystemCommand("Change model", "Switch the active model", self._cmd_prompt_change_model)
        yield SystemCommand("Show keyboard shortcuts", "Open the help screen", self.action_show_help)

    def _cmd_add_selected_to_context(self) -> None:
        node = self.query_one(ProjectTree).cursor_node
        if node is not None and node.data is not None and node.data.path.is_file():
            self.request_context_toggle(str(node.data.path), True)

    def _cmd_remove_selected_from_context(self) -> None:
        node = self.query_one(ProjectTree).cursor_node
        if node is not None and node.data is not None and node.data.path.is_file():
            self.request_context_toggle(str(node.data.path), False)

    def _cmd_toggle_auto_context(self) -> None:
        self.service.toggle_auto_context()
        self._refresh_context_panel()
        self._save_session()

    def _cmd_list_models(self) -> None:
        tool_output = self.query_one(ToolOutput)
        tool_output.command_header("models")
        models = self.provider.list_models()
        if not models:
            tool_output.line("[dim]No models found (or this provider doesn't support discovery)[/dim]")
        else:
            current = self.provider.info().model_name
            for m in models:
                is_current = m.name == current or (m.path and Path(m.path).name == current)
                marker = "[green]✓[/green]" if is_current else " "
                size = f" ({m.size / (1024 * 1024):.0f} MB)" if m.size else ""
                tool_output.line(f"  {marker} {m.name}{size}")

    def _cmd_prompt_change_model(self) -> None:
        current = self.provider.info().model_name
        self.push_screen(
            CommandInputScreen("Switch to model:", placeholder="model name or path", initial=current),
            callback=self._on_change_model_entered,
        )

    def _on_change_model_entered(self, name: Optional[str]) -> None:
        if not name:
            return
        try:
            self.provider.set_model(name)
        except NotImplementedError as exc:
            self.query_one(ConversationView).add_error(str(exc))
            return
        self._refresh_status_bar("idle" if not self._generating else "generating...")
        self.query_one(ConversationView).add_system_message(f"Switched to model: {self.provider.info().model_name}")

    def action_quit(self) -> None:
        self._save_session()
        self.exit()


def build_tui_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-coder tui", description="Launch the PI-AI-CODER Textual workspace")
    parser.add_argument("--project", default=".", help="Project directory to open (default: current directory)")
    parser.add_argument("-m", "--model", default=None, help="Path to GGUF model file, for the llama.cpp provider")
    parser.add_argument("--llama-dir", default=None, help="Path to llama.cpp directory")
    parser.add_argument("--provider", choices=["llama_cpp", "ollama"], default=None, help="Model backend to use")
    parser.add_argument("--ollama-host", default=None, help="Ollama server URL")
    parser.add_argument("--ollama-model", default=None, help="Model name/tag to use with the Ollama provider")
    parser.add_argument("--profile", default=None, help="Named host profile to apply from config.yaml")
    parser.add_argument("--config", default=None, help="Path to a config YAML file")
    parser.add_argument("--fake-model", action="store_true", help="Use the deterministic fake model backend")
    return parser


def run_tui(argv: Optional[List[str]] = None) -> None:
    parser = build_tui_arg_parser()
    args = parser.parse_args(argv)

    project_root = str(Path(args.project).resolve())
    config = load_config(
        config_path=args.config,
        project_dir=project_root,
        profile=args.profile,
        cli_overrides={
            "model.path": args.model,
            "model.llama_cpp_dir": args.llama_dir,
            "model.provider": args.provider,
            "ollama.host": args.ollama_host,
            "ollama.model": args.ollama_model,
        },
    )

    if not args.fake_model and config.model.provider in ("llama_cpp", "llama.cpp", "llamacpp"):
        if not Path(config.model.path).exists():
            print(f"Error: Model not found: {config.model.path}", file=sys.stderr)
            print("Use --fake-model to try the TUI without a real model, or pass --model / set config.yaml.", file=sys.stderr)
            print("Or use Ollama instead: --provider ollama --ollama-model <name>", file=sys.stderr)
            sys.exit(1)

    app = PiAiCoderApp(project_root=project_root, config=config, fake_model=args.fake_model)
    app.run()


if __name__ == "__main__":
    run_tui()
