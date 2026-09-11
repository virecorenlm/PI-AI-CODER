"""Lightweight session persistence.

Stores conversation/session state as JSON under a project-local
``.pi-ai-coder/`` directory (gitignored) so restarting inside the same
project can restore recent conversation, manually selected context files,
and UI preferences -- without needing a database.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_DIR_NAME = ".pi-ai-coder"
STATE_FILE_NAME = "session.json"
MAX_RECENT_PROMPTS = 50
MAX_CONVERSATION_TURNS = 40  # stored turns (user+assistant messages combined)


@dataclass
class SessionState:
    context_files: List[str] = field(default_factory=list)
    auto_context: bool = True
    recent_prompts: List[str] = field(default_factory=list)
    conversation: List[Dict[str, str]] = field(default_factory=list)
    ui: Dict[str, Any] = field(default_factory=dict)

    def add_prompt(self, prompt: str) -> None:
        self.recent_prompts.append(prompt)
        self.recent_prompts = self.recent_prompts[-MAX_RECENT_PROMPTS:]

    def add_turn(self, role: str, content: str) -> None:
        self.conversation.append({"role": role, "content": content})
        self.conversation = self.conversation[-MAX_CONVERSATION_TURNS:]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class SessionStore:
    """Reads/writes a project's SessionState to ``<project>/.pi-ai-coder/session.json``."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.state_dir = self.project_root / STATE_DIR_NAME
        self.state_file = self.state_dir / STATE_FILE_NAME

    def load(self) -> SessionState:
        if not self.state_file.exists():
            return SessionState()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return SessionState()
        return SessionState.from_dict(data)

    def save(self, state: SessionState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")

    def ensure_gitignored(self) -> bool:
        """Best-effort: make sure the project .gitignore excludes our state dir.

        Only touches ``.gitignore`` if it exists and doesn't already ignore
        the state dir; returns True if it modified the file, so callers can
        tell the user rather than editing it silently.
        """
        gitignore = self.project_root / ".gitignore"
        if not gitignore.exists():
            return False
        entry = f"{STATE_DIR_NAME}/"
        try:
            existing = gitignore.read_text(encoding="utf-8")
            if entry in existing:
                return False
            with open(gitignore, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(f"\n# PI-AI-CODER session state\n{entry}\n")
            return True
        except OSError:
            return False
