#!/usr/bin/env python3
"""
Code Assistant CLI - Main Application
Local AI coding assistant with pluggable model backends (llama.cpp, Ollama)

This is now a thin CLI on top of the ``pi_ai_coder`` service layer
(context management, model providers, tools, session state) so the same
backend can also power the Textual TUI (``pi_ai_coder.tui``). Existing
commands and one-shot/interactive workflows behave the same as before.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from pi_ai_coder.agent import AgentEventType, AgentService, ToolRegistry, describe_tool_call
from pi_ai_coder.agent.display import LiveProseFilter
from pi_ai_coder.agent.protocol import ToolCall
from pi_ai_coder.config import AppConfig, load_config
from pi_ai_coder.context import ContextManager
from pi_ai_coder.core import AssistantService, ProjectRootError, SessionState, resolve_project_root
from pi_ai_coder.models import create_provider
from pi_ai_coder.tools import FileTool, GitTool, SearchTool, ShellTool
from pi_ai_coder.tools.base import RiskLevel


class CodeAssistantCLI:
    """Main CLI application"""

    COMMANDS = {
        'add': 'Add file(s) to context',
        'remove': 'Remove file(s) from context',
        'files': 'List context files',
        'clear': 'Clear context',
        'auto': 'Toggle auto context detection',
        'exec': 'Execute shell command',
        'save': 'Save last code block to file',
        'diff': 'Show git diff',
        'models': 'List models available for the current provider',
        'model': 'Show or switch the active model (e.g. `model qwen3.5:latest`)',
        'reset': 'Reset conversation',
        'help': 'Show this help',
        'quit': 'Exit'
    }

    def __init__(self,
                 config: Optional[AppConfig] = None,
                 fake_model: bool = False,
                 project_root: Optional[str] = None,
                 use_agent: bool = True):

        self.config = config or load_config()
        self.verbose = False
        self.use_agent = use_agent
        self.project_root = resolve_project_root(project_root) if project_root else Path.cwd()

        self.context_manager = ContextManager(
            max_file_size_kb=self.config.project.max_file_size_kb
        )

        provider = create_provider(self.config, fake_model=fake_model)

        session = SessionState(auto_context=self.config.project.auto_context)
        self.service = AssistantService(
            provider=provider,
            context_manager=self.context_manager,
            session=session,
            project_root=str(self.project_root),
        )

        self.shell_tool = ShellTool(cwd=str(self.project_root))
        self.git_tool = GitTool(cwd=str(self.project_root))
        self.file_tool = FileTool(project_root=str(self.project_root), should_ignore=self.context_manager.should_ignore)
        self.search_tool = SearchTool(project_root=str(self.project_root), should_ignore=self.context_manager.should_ignore)

        self.tool_registry = ToolRegistry(
            project_root=str(self.project_root),
            file_tool=self.file_tool,
            git_tool=self.git_tool,
            search_tool=self.search_tool,
        )
        self.agent = AgentService(
            provider=provider,
            tools=self.tool_registry,
            session=session,
            project_root=str(self.project_root),
            approve=self._approve_tool_call,
        )

    def _approve_tool_call(self, tool_call: ToolCall, risk: RiskLevel) -> bool:
        print(f"\n⚠ Approval required ({risk.value}): {describe_tool_call(tool_call.name, tool_call.arguments)}")
        try:
            answer = input("  Allow this? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes")

    @property
    def state_context_files(self) -> List[str]:
        return self.service.session.context_files

    def handle_command(self, cmd: str) -> bool:
        """Handle special commands. Returns True if should continue, False if quit"""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == 'quit' or command == 'q':
            return False

        elif command == 'help' or command == 'h':
            print("\nAvailable commands:")
            for name, desc in self.COMMANDS.items():
                print(f"  {name:12} - {desc}")

        elif command == 'add':
            patterns = args.split()
            new_files = []
            for pattern in patterns:
                new_files.extend(str(f) for f in self.project_root.glob(pattern))
            self.service.add_context_files(new_files)
            print(f"✓ {len(self.state_context_files)} files in context")

        elif command == 'remove':
            patterns = args.split()
            for pattern in patterns:
                self.service.remove_context_files(pattern)
            print(f"✓ {len(self.state_context_files)} files in context")

        elif command == 'files':
            if self.state_context_files:
                print("\nContext files:")
                for f in self.state_context_files:
                    size_kb = Path(f).stat().st_size / 1024
                    print(f"  • {f} ({size_kb:.1f} KB)")
            else:
                print("No files in context")

        elif command == 'clear':
            self.service.clear_context_files()
            print("✓ Context cleared")

        elif command == 'auto':
            enabled = self.service.toggle_auto_context()
            status = "enabled" if enabled else "disabled"
            print(f"✓ Auto context detection {status}")

        elif command == 'reset':
            self.service.reset()
            print("✓ Conversation reset")

        elif command == 'exec':
            result = self.shell_tool.run(args)
            if result.output:
                print(result.output)
            if result.error:
                print(f"stderr: {result.error}", file=sys.stderr)
            if not result.success and not result.error:
                print(f"Error: command failed (exit code {result.exit_code})", file=sys.stderr)

        elif command == 'save':
            code_blocks = self.agent.last_code_blocks if self.use_agent else self.service.last_code_blocks
            if not code_blocks:
                print("No code blocks in last response")
            else:
                filename = args or "output.txt"
                code = code_blocks[0]['code']
                # The user typed this exact path, so it's explicit intent --
                # not subject to the project-boundary restriction (which
                # exists for automated/model-driven writes).
                result = self.file_tool.save(filename, code, restrict_to_project=False)
                if result.success:
                    print(f"✓ Saved to {filename}")
                else:
                    print(f"✗ {result.error}", file=sys.stderr)

        elif command == 'diff':
            if not self.git_tool.is_repo():
                print("Not a git repository")
            else:
                result = self.git_tool.diff()
                print(result.output if result.output else "No changes")

        elif command == 'models':
            models = self.service.provider.list_models()
            if not models:
                print("No models found (or this provider doesn't support discovery)")
            else:
                current = self.service.provider.info().model_name
                for m in models:
                    is_current = m.name == current or (m.path and Path(m.path).name == current)
                    marker = "✓" if is_current else " "
                    size = f" ({m.size / (1024 * 1024):.0f} MB)" if m.size else ""
                    print(f"  {marker} {m.name}{size}")

        elif command == 'model':
            if not args:
                print(f"Current model: {self.service.provider.info().model_name}")
            else:
                try:
                    self.service.provider.set_model(args.strip())
                    print(f"✓ Switched to {self.service.provider.info().model_name}")
                except NotImplementedError as e:
                    print(f"✗ {e}", file=sys.stderr)

        else:
            print(f"Unknown command: {command}. Type 'help' for commands.")

        return True

    def process_query(self, query: str):
        """Process a user query: runs the full agent loop (inspect, edit,
        run commands, iterate) by default, or plain one-shot chat with
        --no-agent."""
        if self.use_agent:
            self.run_agent_task(query)
            return

        files, auto_used = self.service.resolve_context_files(query)

        if auto_used and files and self.verbose:
            print(f"[Auto-discovered {len(files)} files]")

        if self.verbose and files:
            print(f"[Building context from {len(files)} files...]")

        print()  # Newline before response

        try:
            response = self.service.chat(query)
            print(response)

            if self.verbose:
                context = self.service.build_context(files, query)
                print(f"[Context: {len(context)} chars]")

        except Exception as e:
            print(f"\n✗ Error: {e}", file=sys.stderr)

    def run_agent_task(self, query: str):
        """Run the agent loop for one task, rendering its events to the terminal."""
        print()
        prose_filter = LiveProseFilter()
        streamed_any = False

        try:
            for event in self.agent.run_task(query, hint_files=self.service.session.context_files or None):
                t = event.type

                if t == AgentEventType.TOKEN:
                    visible = prose_filter.feed(event.data["text"])
                    if visible:
                        print(visible, end="", flush=True)
                        streamed_any = True

                elif t == AgentEventType.TOOL_REQUESTED:
                    if streamed_any:
                        print()
                        streamed_any = False
                    print(f"● {describe_tool_call(event.data['tool'], event.data['arguments'])}")
                    prose_filter = LiveProseFilter()

                elif t == AgentEventType.TOOL_FINISHED:
                    if event.data["tool"] in ("run_command", "run_tests"):
                        output = (event.data.get("output") or "").strip()
                        if output:
                            for line in output.splitlines():
                                print(f"  {line}")
                    if not event.data["success"]:
                        print(f"  ✗ {event.data.get('error') or 'failed'}")

                elif t == AgentEventType.ITERATION_LIMIT:
                    print(f"  (stopped: {event.data['reason']} limit reached)")

                elif t == AgentEventType.FAILED:
                    if streamed_any:
                        print()
                    print(f"✗ {event.data.get('error', 'Agent task failed')}", file=sys.stderr)

                elif t == AgentEventType.CANCELLED:
                    print("\n(cancelled)")

                elif t == AgentEventType.COMPLETED:
                    if streamed_any:
                        print()

        except KeyboardInterrupt:
            self.agent.cancel()
            print("\n(cancelled)")

    def interactive_mode(self):
        """Run interactive REPL"""
        print("╔═══════════════════════════════════════════╗")
        print("║   Code Assistant - Local AI              ║")
        print("╚═══════════════════════════════════════════╝")
        print(f"Project: {self.project_root}")
        print("\nType your question or 'help' for commands\n")

        while True:
            try:
                user_input = input("\n>>> ").strip()

                if not user_input:
                    continue

                if user_input.startswith('/') or user_input.split()[0] in self.COMMANDS:
                    cmd = user_input[1:] if user_input.startswith('/') else user_input
                    should_continue = self.handle_command(cmd)
                    if not should_continue:
                        break
                else:
                    self.process_query(user_input)

            except KeyboardInterrupt:
                print("\n\nGoodbye! (Use 'quit' to exit cleanly)")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"\n✗ Unexpected error: {e}", file=sys.stderr)

    def one_shot_mode(self, query: str, files: List[str]):
        """Run single query and exit"""
        self.service.session.context_files = files
        self.service.session.auto_context = not bool(files)  # Only auto if no files specified

        self.process_query(query)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local AI Code Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  %(prog)s

  # With specific files
  %(prog)s main.py utils.py -q "Refactor this code"

  # One-shot query
  %(prog)s -q "Write a binary search function"

  # Custom llama.cpp model
  %(prog)s --model ./models/deepseek-coder.gguf

  # Use Ollama instead of llama.cpp
  %(prog)s --provider ollama --ollama-model qwen3.5:latest

  # Use a named host profile from config.yaml
  %(prog)s --profile asrock

  # Operate on a different project directory than the current one
  %(prog)s --project ~/GITHUB/some-other-repo

  # Full-screen TUI workspace
  %(prog)s tui

  # Try the TUI/CLI without a real model
  %(prog)s tui --fake-model

  # Plain queries run the full agent loop (inspect/edit/test) by default;
  # --no-agent falls back to simple one-shot chat with no tool use
  %(prog)s -q "Add input validation to the registration endpoint" --no-agent
        """
    )

    parser.add_argument(
        'files',
        nargs='*',
        help='Files to include in context'
    )

    parser.add_argument(
        '--project',
        default='.',
        help='Project/workspace directory to operate on (default: current directory)'
    )

    parser.add_argument(
        '-m', '--model',
        default=None,
        help='Path to GGUF model file, for the llama.cpp provider (default: from config)'
    )

    parser.add_argument(
        '-q', '--query',
        help='Run single query and exit'
    )

    parser.add_argument(
        '-t', '--temperature',
        type=float,
        default=None,
        help='Model temperature (0.0-1.0, default: from config, or 0.1)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--llama-dir',
        default=None,
        help='Path to llama.cpp directory (default: from config, or ./llama.cpp)'
    )

    parser.add_argument(
        '--provider',
        choices=['llama_cpp', 'ollama'],
        default=None,
        help='Model backend to use (default: from config, or llama_cpp)'
    )

    parser.add_argument(
        '--ollama-host',
        default=None,
        help='Ollama server URL (default: from config, or http://127.0.0.1:11434)'
    )

    parser.add_argument(
        '--ollama-model',
        default=None,
        help='Model name/tag to use with the Ollama provider (e.g. qwen3.5:latest)'
    )

    parser.add_argument(
        '--profile',
        default=None,
        help='Named host profile to apply from config.yaml (see config.example.yaml)'
    )

    parser.add_argument(
        '--config',
        default=None,
        help='Path to a config YAML file (default: auto-detected config.yaml in the project)'
    )

    parser.add_argument(
        '--fake-model',
        action='store_true',
        help='Use a deterministic fake model backend (no llama.cpp/GGUF/Ollama needed) for testing'
    )

    parser.add_argument(
        '--no-agent',
        action='store_true',
        help='Disable the agent/tool loop; queries get a plain one-shot chat response instead'
    )

    return parser


def main():
    parser = build_arg_parser()

    # 'tui' is a subcommand, not a context file -- handle it before the
    # positional-files argparse config (which would otherwise swallow it).
    if len(sys.argv) > 1 and sys.argv[1] == 'tui':
        from pi_ai_coder.tui.app import run_tui
        run_tui(sys.argv[2:])
        return

    args = parser.parse_args()

    try:
        project_root = resolve_project_root(args.project)
    except ProjectRootError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    config = load_config(
        config_path=args.config,
        project_dir=str(project_root),
        profile=args.profile,
        cli_overrides={
            "model.path": args.model,
            "model.temperature": args.temperature,
            "model.llama_cpp_dir": args.llama_dir,
            "model.provider": args.provider,
            "ollama.host": args.ollama_host,
            "ollama.model": args.ollama_model,
        },
    )

    if not args.fake_model and config.model.provider in ("llama_cpp", "llama.cpp", "llamacpp"):
        if not Path(config.model.path).exists():
            print(f"Error: Model not found: {config.model.path}", file=sys.stderr)
            print("\nDownload a model first:", file=sys.stderr)
            print("  mkdir -p models", file=sys.stderr)
            print("  cd models", file=sys.stderr)
            print("  wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf", file=sys.stderr)
            print("\nOr use Ollama instead: --provider ollama --ollama-model <name>", file=sys.stderr)
            sys.exit(1)

    try:
        app = CodeAssistantCLI(
            config=config,
            fake_model=args.fake_model,
            project_root=str(project_root),
            use_agent=not args.no_agent,
        )
        app.verbose = args.verbose

    except Exception as e:
        print(f"Error initializing: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.fake_model:
        health = app.service.provider.health_check()
        if not health.available:
            print(f"Warning: {health.message}", file=sys.stderr)

    if args.query:
        app.one_shot_mode(args.query, args.files)
    else:
        if args.files:
            app.service.session.context_files = args.files
            print(f"Loaded {len(args.files)} files into context")

        app.interactive_mode()


if __name__ == "__main__":
    main()
