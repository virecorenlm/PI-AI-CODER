#!/usr/bin/env python3
"""
Optimized llama.cpp model runner
Handles streaming, parameters, and response parsing
"""

import subprocess
import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Generator
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Model configuration parameters"""
    model_path: str
    n_ctx: int = 4096          # Context window
    n_predict: int = 1024      # Max tokens to generate
    temperature: float = 0.1   # Lower = more deterministic
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    threads: int = 4           # Pi 5 has 4 cores
    batch_size: int = 512
    n_gpu_layers: int = 0      # Pi doesn't have CUDA
    
    def to_llama_args(self) -> list:
        """Convert config to llama.cpp CLI arguments"""
        return [
            "-m", self.model_path,
            "--ctx-size", str(self.n_ctx),
            "-n", str(self.n_predict),
            "--temp", str(self.temperature),
            "--top-p", str(self.top_p),
            "--top-k", str(self.top_k),
            "--repeat-penalty", str(self.repeat_penalty),
            "-t", str(self.threads),
            "-b", str(self.batch_size),
            "--n-gpu-layers", str(self.n_gpu_layers),
        ]


class LlamaRunner:
    """Handles llama.cpp execution"""
    
    def __init__(self, 
                 llama_cpp_dir: str = "./llama.cpp",
                 config: Optional[ModelConfig] = None):
        self.llama_cpp_dir = Path(llama_cpp_dir)
        self.main_executable = self.llama_cpp_dir / "main"
        
        if not self.main_executable.exists():
            raise FileNotFoundError(
                f"llama.cpp main not found at {self.main_executable}. "
                "Run: cd llama.cpp && make"
            )
        
        self.config = config or ModelConfig(
            model_path="./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        )
    
    def format_prompt(self, 
                     system: str,
                     user_message: str,
                     context: str = "") -> str:
        """Format prompt for Qwen2.5-Coder (ChatML format)"""
        prompt = f"""<|im_start|>system
{system}<|im_end|>
<|im_start|>user
"""
        
        if context:
            prompt += f"""Here are the relevant files:

{context}

"""
        
        prompt += f"""{user_message}<|im_end|>
<|im_start|>assistant
"""
        return prompt
    
    def run_inference(self, 
                     prompt: str,
                     stream: bool = False) -> str:
        """Run inference with llama.cpp"""
        
        # Build command
        cmd = [str(self.main_executable)]
        cmd.extend(self.config.to_llama_args())
        cmd.extend([
            "-p", prompt,
            "--log-disable",  # Less noise
        ])
        
        # Add streaming if requested
        if not stream:
            cmd.append("--no-display-prompt")
        
        try:
            # Run llama.cpp
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.llama_cpp_dir.parent),
                timeout=300  # 5 min timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"llama.cpp failed: {result.stderr}")
            
            # Parse output
            output = result.stdout
            
            # Remove prompt echo if present
            if "<|im_start|>assistant" in output:
                output = output.split("<|im_start|>assistant")[-1]
            
            # Clean up end tokens
            output = output.replace("<|im_end|>", "").strip()
            
            return output
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Model inference timed out (>5 min)")
        except Exception as e:
            raise RuntimeError(f"Inference failed: {str(e)}")
    
    def run_streaming(self, prompt: str) -> Generator[str, None, None]:
        """Stream tokens as they're generated"""
        cmd = [str(self.main_executable)]
        cmd.extend(self.config.to_llama_args())
        cmd.extend([
            "-p", prompt,
            "--log-disable",
        ])
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(self.llama_cpp_dir.parent)
        )
        
        try:
            for line in process.stdout:
                # Filter out llama.cpp debug output
                if not line.startswith("[") and line.strip():
                    yield line
        finally:
            process.terminate()
            process.wait()
    
    def extract_code_blocks(self, response: str) -> list:
        """Extract code blocks from response"""
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        return [{'language': lang or 'text', 'code': code.strip()} 
                for lang, code in matches]
    
    def validate_model(self) -> bool:
        """Quick validation that model works"""
        try:
            test_prompt = self.format_prompt(
                system="You are a helpful assistant.",
                user_message="Say 'OK' if you can read this."
            )
            
            response = self.run_inference(test_prompt)
            return len(response) > 0
            
        except Exception as e:
            print(f"Model validation failed: {e}")
            return False


class ConversationManager:
    """Manages multi-turn conversations with context"""
    
    def __init__(self, runner: LlamaRunner, max_history: int = 5):
        self.runner = runner
        self.history = []
        self.max_history = max_history
        self.system_prompt = """You are Claude Code, an expert coding assistant running locally on a Raspberry Pi.

Your capabilities:
- Reading and analyzing code files
- Suggesting improvements and refactoring
- Debugging and explaining errors
- Writing new code and documentation
- Following best practices

You respond concisely but thoroughly. When showing code, use proper formatting with language tags."""
    
    def add_turn(self, user_msg: str, assistant_msg: str):
        """Add a conversation turn to history"""
        self.history.append({
            'user': user_msg,
            'assistant': assistant_msg
        })
        
        # Keep only recent history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def build_conversation_prompt(self, 
                                 user_message: str,
                                 context: str = "") -> str:
        """Build prompt with conversation history"""
        
        # Start with system
        prompt = f"<|im_start|>system\n{self.system_prompt}<|im_end|>\n"
        
        # Add history
        for turn in self.history:
            prompt += f"<|im_start|>user\n{turn['user']}<|im_end|>\n"
            prompt += f"<|im_start|>assistant\n{turn['assistant']}<|im_end|>\n"
        
        # Add current turn with context
        prompt += "<|im_start|>user\n"
        
        if context:
            prompt += f"Here are the relevant files:\n\n{context}\n\n"
        
        prompt += f"{user_message}<|im_end|>\n<|im_start|>assistant\n"
        
        return prompt
    
    def chat(self, user_message: str, context: str = "") -> str:
        """Send a message and get response"""
        prompt = self.build_conversation_prompt(user_message, context)
        response = self.runner.run_inference(prompt)
        
        # Store in history
        self.add_turn(user_message, response)
        
        return response
    
    def reset(self):
        """Clear conversation history"""
        self.history = []


if __name__ == "__main__":
    # Test the runner
    print("Testing llama.cpp runner...")
    
    config = ModelConfig(
        model_path="./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        n_predict=100,
        temperature=0.2
    )
    
    runner = LlamaRunner(config=config)
    
    print("Validating model...")
    if runner.validate_model():
        print("✓ Model validated successfully")
        
        # Test conversation
        conv = ConversationManager(runner)
        response = conv.chat("Write a Python function to reverse a string.")
        print(f"\nResponse:\n{response}")
        
        # Extract code
        code_blocks = runner.extract_code_blocks(response)
        if code_blocks:
            print(f"\n✓ Found {len(code_blocks)} code block(s)")
    else:
        print("✗ Model validation failed")
