"""Keyboard shortcuts / help screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

HELP_TEXT = """\
[bold]PI-AI-CODER -- keyboard shortcuts[/bold]

[bold]Global[/bold]
  ctrl+p        command palette
  ctrl+o        focus project tree
  ctrl+l        focus prompt composer
  ctrl+g        focus git panel
  ctrl+t        focus tool output
  ctrl+d        view changes (git diff)
  ctrl+r        reset conversation
  ctrl+k        clear manual context
  f1            this help screen
  ctrl+c        cancel the running agent task
  ctrl+q        quit

[bold]Project tree[/bold]
  enter         preview selected file
  a             add selected file to AI context
  d             remove selected file from AI context

[bold]Prompt composer[/bold]
  enter         newline
  ctrl+j        submit (most terminals send this for Ctrl+Enter)
  ctrl+up/down  browse prompt history
  escape        unfocus the composer

[bold]File preview[/bold]
  a / d         add / remove file from context
  escape, q     close preview

[bold]Coding agent[/bold]
  Typing a request in the prompt runs the full agent loop: it inspects
  the project, searches code, reads files, edits them (create/patch/
  write/delete/move), runs commands/tests, and iterates until done --
  shown as "● action" lines in the conversation. Reads and ordinary edits
  happen automatically; a shell command that looks destructive (rm -rf,
  git reset --hard, force pushes, ...) pauses for an approval dialog
  first. Use ctrl+d or the git panel to review what changed; PI-AI-CODER
  never commits, pushes, or discards changes on its own.

[bold]Model provider[/bold]
  Use the command palette's "List models" / "Change model" to switch
  models within the current provider (llama.cpp or Ollama). Switching
  the *provider* itself (llama.cpp <-> Ollama) requires a restart with
  --provider, since the two backends work very differently.

[bold]Known limitations (this iteration)[/bold]
  - No in-place file editing in the preview pane (it's read-only; the
    agent's own file tools are how edits actually happen).
  - The agent's tool-calling uses a text-based protocol understood by
    any capable model, not a given provider's native function-calling.
  - No checkpoint/undo system yet beyond git itself -- review with
    ctrl+d before committing.

Press escape or q to close this screen.
"""


class HelpScreen(Screen):
    BINDINGS = [Binding("escape,q,f1", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(HELP_TEXT)
        yield Footer()
