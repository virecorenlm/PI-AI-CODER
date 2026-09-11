"""PI-AI-CODER: a local-first coding assistant for Linux hosts, from a
Raspberry Pi 5 to a full workstation.

This package holds the reusable application core (context management,
model providers, tools, session state) that both the CLI (``assistant.py``)
and the Textual TUI (``pi_ai_coder.tui``) are built on top of. Hardware and
backend choices (llama.cpp vs. Ollama, thread counts, context sizes) are
configuration-driven -- see ``pi_ai_coder.config`` -- not hard-coded here.
"""

__version__ = "0.2.0"
