"""Application core: orchestrates context, the model provider, and session
state. Both the CLI (``assistant.py``) and the Textual TUI call into this
service instead of talking to a model or the context manager directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from pi_ai_coder.context.manager import ContextManager
from pi_ai_coder.core.events import AssistantStatus, EventType, StreamEvent
from pi_ai_coder.core.session import SessionState
from pi_ai_coder.models.base import Message, ModelProvider, extract_code_blocks

DEFAULT_SYSTEM_PROMPT = """You are Claude Code, an expert coding assistant running locally on your machine.

Your capabilities:
- Reading and analyzing code files
- Suggesting improvements and refactoring
- Debugging and explaining errors
- Writing new code and documentation
- Following best practices

You respond concisely but thoroughly. When showing code, use proper formatting with language tags."""

# Default extensions scanned when no keyword-specific extension is detected.
DEFAULT_EXTENSIONS = ['.py', '.js', '.rs', '.go', '.java', '.cpp', '.c', '.h']
KEYWORD_EXTENSIONS = {
    'python': ['.py'],
    '.py': ['.py'],
    'javascript': ['.js', '.jsx'],
    '.js': ['.js', '.jsx'],
    'rust': ['.rs'],
    '.rs': ['.rs'],
}
MAX_AUTO_DISCOVERED_FILES = 10


class AssistantService:
    """Ties context selection, model streaming, and session state together."""

    def __init__(
        self,
        provider: ModelProvider,
        context_manager: ContextManager,
        session: SessionState,
        project_root: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_history_turns: int = 5,
    ):
        self.provider = provider
        self.context_manager = context_manager
        self.session = session
        self.project_root = Path(project_root or Path.cwd())
        self.system_prompt = system_prompt
        self.max_history_turns = max_history_turns
        self.last_code_blocks: list = []

    # -- context selection -------------------------------------------------

    def discover_project_files(self, query: str) -> List[str]:
        """Auto-discover relevant files based on keywords in the query."""
        query_lower = query.lower()
        extensions: List[str] = []
        for keyword, exts in KEYWORD_EXTENSIONS.items():
            if keyword in query_lower:
                for ext in exts:
                    if ext not in extensions:
                        extensions.append(ext)

        if not extensions:
            extensions = DEFAULT_EXTENSIONS

        files: List[str] = []
        for ext in extensions:
            files.extend(
                str(f) for f in self.project_root.rglob(f'*{ext}')
                if not self.context_manager.should_ignore(f)
            )

        return files[:MAX_AUTO_DISCOVERED_FILES]

    def resolve_context_files(self, query: str) -> Tuple[List[str], bool]:
        """Return (files, auto_discovered) for the given query."""
        files = list(self.session.context_files)
        if self.session.auto_context and not files:
            return self.discover_project_files(query), True
        return files, False

    def build_context(self, files: List[str], query: str) -> str:
        if not files:
            return ""
        return self.context_manager.build_context(files, query)

    # -- context file management (mirrors old add/remove/files/clear) ------

    def add_context_files(self, paths: List[str]) -> None:
        for path in paths:
            if path not in self.session.context_files:
                self.session.context_files.append(path)

    def remove_context_files(self, pattern: str) -> None:
        self.session.context_files = [
            f for f in self.session.context_files if pattern not in f
        ]

    def clear_context_files(self) -> None:
        self.session.context_files = []

    def toggle_auto_context(self) -> bool:
        self.session.auto_context = not self.session.auto_context
        return self.session.auto_context

    # -- message assembly ---------------------------------------------------

    def _build_messages(self, user_message: str, context: str) -> List[Message]:
        messages = [Message("system", self.system_prompt)]
        for turn in self.session.conversation[-(self.max_history_turns * 2):]:
            messages.append(Message(turn["role"], turn["content"]))

        content = user_message
        if context:
            content = f"Here are the relevant files:\n\n{context}\n\n{user_message}"
        messages.append(Message("user", content))
        return messages

    # -- chat -----------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """Blocking chat call. Preserves the old CLI's exact behavior."""
        files, _ = self.resolve_context_files(user_message)
        context = self.build_context(files, user_message)
        messages = self._build_messages(user_message, context)

        response = self.provider.chat(messages)

        self.session.add_turn("user", user_message)
        self.session.add_turn("assistant", response)
        self.session.add_prompt(user_message)
        self.last_code_blocks = extract_code_blocks(response)
        return response

    def stream_chat(self, user_message: str) -> Iterator[StreamEvent]:
        """Streaming chat call, yielding status/token/error/done events."""
        yield StreamEvent(EventType.STATUS, data={"status": AssistantStatus.BUILDING_CONTEXT})

        files, auto_discovered = self.resolve_context_files(user_message)
        context = self.build_context(files, user_message)
        if files:
            yield StreamEvent(
                EventType.STATUS,
                data={
                    "status": AssistantStatus.BUILDING_CONTEXT,
                    "files": files,
                    "auto_discovered": auto_discovered,
                    "context_chars": len(context),
                },
            )

        messages = self._build_messages(user_message, context)

        yield StreamEvent(EventType.STATUS, data={"status": AssistantStatus.GENERATING})

        collected: List[str] = []
        finished_cleanly = False
        for event in self.provider.stream_chat(messages):
            if event.type == EventType.TOKEN:
                collected.append(event.text)
            elif event.type == EventType.DONE:
                finished_cleanly = True
            yield event

        full_response = "".join(collected)
        if full_response and (finished_cleanly or collected):
            self.session.add_turn("user", user_message)
            self.session.add_turn("assistant", full_response)
            self.session.add_prompt(user_message)
            self.last_code_blocks = extract_code_blocks(full_response)

    def cancel(self) -> None:
        self.provider.cancel()

    def reset(self) -> None:
        self.session.conversation = []
        self.last_code_blocks = []
