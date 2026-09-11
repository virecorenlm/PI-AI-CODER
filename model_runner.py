#!/usr/bin/env python3
"""Backward-compatibility shim.

Model execution now lives in ``pi_ai_coder.models`` behind the
``ModelProvider`` interface (see ``pi_ai_coder.models.llama_cpp_provider``
and ``pi_ai_coder.models.fake_provider``). This module re-implements the
original ``LlamaRunner``/``ConversationManager``/``ModelConfig`` API as
thin adapters on top of that new code, so anything that still imports
``model_runner`` directly keeps working. New code should use
``pi_ai_coder.models`` and ``pi_ai_coder.core.assistant_service`` instead.
"""

from typing import Generator, Optional

from pi_ai_coder.models.base import ModelConfig, Message, extract_code_blocks as _extract_code_blocks
from pi_ai_coder.models.llama_cpp_provider import LlamaCppProvider

__all__ = ["ModelConfig", "LlamaRunner", "ConversationManager"]


class LlamaRunner:
    """Adapter preserving the original LlamaRunner API."""

    def __init__(self, llama_cpp_dir: str = "./llama.cpp", config: Optional[ModelConfig] = None):
        self._provider = LlamaCppProvider(llama_cpp_dir=llama_cpp_dir, config=config)
        self.llama_cpp_dir = self._provider.llama_cpp_dir
        self.main_executable = self._provider.executable
        self.config = self._provider.config

    def format_prompt(self, system: str, user_message: str, context: str = "") -> str:
        """Format prompt for Qwen2.5-Coder (ChatML format)"""
        content = user_message
        if context:
            content = f"Here are the relevant files:\n\n{context}\n\n{user_message}"
        messages = [Message("system", system), Message("user", content)]
        return self._provider.format_prompt(messages)

    def run_inference(self, prompt: str, stream: bool = False) -> str:
        """Run inference with llama.cpp on an already-formatted prompt."""
        return self._provider.run_raw(prompt)

    def run_streaming(self, prompt: str) -> Generator[str, None, None]:
        """Stream raw text chunks as they're generated."""
        from pi_ai_coder.core.events import EventType

        cmd = self._provider._build_command(prompt)  # noqa: SLF001 - intentional legacy adapter
        import subprocess

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(self._provider.llama_cpp_dir.parent),
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if line.strip():
                    yield line
        finally:
            process.terminate()
            process.wait()

    def extract_code_blocks(self, response: str) -> list:
        """Extract code blocks from response"""
        return _extract_code_blocks(response)

    def validate_model(self) -> bool:
        """Quick validation that model works"""
        try:
            prompt = self.format_prompt(
                system="You are a helpful assistant.",
                user_message="Say 'OK' if you can read this.",
            )
            response = self.run_inference(prompt)
            return len(response) > 0
        except Exception:
            return False


class ConversationManager:
    """Manages multi-turn conversations with context (adapter)."""

    def __init__(self, runner: LlamaRunner, max_history: int = 5):
        self.runner = runner
        self.history = []
        self.max_history = max_history
        self.system_prompt = """You are Claude Code, an expert coding assistant running locally on your machine.

Your capabilities:
- Reading and analyzing code files
- Suggesting improvements and refactoring
- Debugging and explaining errors
- Writing new code and documentation
- Following best practices

You respond concisely but thoroughly. When showing code, use proper formatting with language tags."""

    def add_turn(self, user_msg: str, assistant_msg: str):
        self.history.append({"user": user_msg, "assistant": assistant_msg})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def build_conversation_prompt(self, user_message: str, context: str = "") -> str:
        messages = [Message("system", self.system_prompt)]
        for turn in self.history:
            messages.append(Message("user", turn["user"]))
            messages.append(Message("assistant", turn["assistant"]))

        content = user_message
        if context:
            content = f"Here are the relevant files:\n\n{context}\n\n{user_message}"
        messages.append(Message("user", content))
        return self.runner._provider.format_prompt(messages)  # noqa: SLF001 - intentional legacy adapter

    def chat(self, user_message: str, context: str = "") -> str:
        prompt = self.build_conversation_prompt(user_message, context)
        response = self.runner.run_inference(prompt)
        self.add_turn(user_message, response)
        return response

    def reset(self):
        self.history = []
