#!/usr/bin/env python3
"""
Code Assistant CLI - Main Application
Local AI coding assistant powered by llama.cpp
"""

import argparse
import sys
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from context_manager import ContextManager
from model_runner import LlamaRunner, ConversationManager, ModelConfig


@dataclass
class AppState:
    """Application state"""
    context_files: List[str]
    auto_context: bool  # Auto-detect relevant files
    verbose: bool
    
    def __init__(self):
        self.context_files = []
        self.auto_context = True
        self.verbose = False


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
        'reset': 'Reset conversation',
        'help': 'Show this help',
        'quit': 'Exit'
    }
    
    def __init__(self, 
                 model_path: str,
                 llama_cpp_dir: str = "./llama.cpp",
                 temperature: float = 0.1):
        
        # Initialize components
        self.context_manager = ContextManager()
        
        config = ModelConfig(
            model_path=model_path,
            temperature=temperature,
            n_predict=2048  # Longer responses for code
        )
        
        self.runner = LlamaRunner(llama_cpp_dir=llama_cpp_dir, config=config)
        self.conversation = ConversationManager(self.runner)
        
        self.state = AppState()
        self.last_code_blocks = []
    
    def discover_project_files(self, query: str) -> List[str]:
        """Auto-discover relevant files based on query"""
        cwd = Path.cwd()
        
        # Look for common patterns in query
        extensions = []
        if 'python' in query.lower() or '.py' in query:
            extensions.append('.py')
        if 'javascript' in query.lower() or '.js' in query:
            extensions.extend(['.js', '.jsx'])
        if 'rust' in query.lower() or '.rs' in query:
            extensions.append('.rs')
        
        # Default to common code files
        if not extensions:
            extensions = ['.py', '.js', '.rs', '.go', '.java', '.cpp', '.c', '.h']
        
        # Find files
        files = []
        for ext in extensions:
            files.extend([str(f) for f in cwd.rglob(f'*{ext}') 
                         if not self.context_manager.should_ignore(f)])
        
        # Limit to reasonable number
        return files[:10]
    
    def handle_command(self, cmd: str) -> bool:
        """Handle special commands. Returns True if should continue, False if quit"""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == 'quit' or command == 'q':
            return False
        
        elif command == 'help' or command == 'h':
            print("\nAvailable commands:")
            for cmd, desc in self.COMMANDS.items():
                print(f"  {cmd:12} - {desc}")
        
        elif command == 'add':
            # Add files to context
            patterns = args.split()
            for pattern in patterns:
                files = list(Path.cwd().glob(pattern))
                for f in files:
                    if str(f) not in self.state.context_files:
                        self.state.context_files.append(str(f))
            print(f"✓ {len(self.state.context_files)} files in context")
        
        elif command == 'remove':
            patterns = args.split()
            for pattern in patterns:
                self.state.context_files = [
                    f for f in self.state.context_files 
                    if pattern not in f
                ]
            print(f"✓ {len(self.state.context_files)} files in context")
        
        elif command == 'files':
            if self.state.context_files:
                print("\nContext files:")
                for f in self.state.context_files:
                    size_kb = Path(f).stat().st_size / 1024
                    print(f"  • {f} ({size_kb:.1f} KB)")
            else:
                print("No files in context")
        
        elif command == 'clear':
            self.state.context_files = []
            print("✓ Context cleared")
        
        elif command == 'auto':
            self.state.auto_context = not self.state.auto_context
            status = "enabled" if self.state.auto_context else "disabled"
            print(f"✓ Auto context detection {status}")
        
        elif command == 'reset':
            self.conversation.reset()
            print("✓ Conversation reset")
        
        elif command == 'exec':
            # Execute shell command
            try:
                result = subprocess.run(
                    args, 
                    shell=True, 
                    capture_output=True, 
                    text=True,
                    timeout=30
                )
                print(result.stdout)
                if result.stderr:
                    print(f"stderr: {result.stderr}", file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}")
        
        elif command == 'save':
            # Save last code block
            if not self.last_code_blocks:
                print("No code blocks in last response")
            else:
                filename = args or "output.txt"
                code = self.last_code_blocks[0]['code']
                with open(filename, 'w') as f:
                    f.write(code)
                print(f"✓ Saved to {filename}")
        
        elif command == 'diff':
            # Show git diff
            try:
                result = subprocess.run(
                    ['git', 'diff'], 
                    capture_output=True, 
                    text=True
                )
                if result.stdout:
                    print(result.stdout)
                else:
                    print("No changes")
            except:
                print("Not a git repository")
        
        else:
            print(f"Unknown command: {command}. Type 'help' for commands.")
        
        return True
    
    def process_query(self, query: str):
        """Process a user query"""
        
        # Auto-discover files if enabled
        files_to_use = self.state.context_files.copy()
        
        if self.state.auto_context and not files_to_use:
            discovered = self.discover_project_files(query)
            if discovered:
                files_to_use = discovered
                if self.state.verbose:
                    print(f"[Auto-discovered {len(discovered)} files]")
        
        # Build context
        context = ""
        if files_to_use:
            if self.state.verbose:
                print(f"[Building context from {len(files_to_use)} files...]")
            
            context = self.context_manager.build_context(files_to_use, query)
            
            if self.state.verbose:
                print(f"[Context: {len(context)} chars]")
        
        # Get response
        print()  # Newline before response
        
        try:
            response = self.conversation.chat(query, context)
            print(response)
            
            # Extract and store code blocks
            self.last_code_blocks = self.runner.extract_code_blocks(response)
            
        except Exception as e:
            print(f"\n✗ Error: {e}", file=sys.stderr)
    
    def interactive_mode(self):
        """Run interactive REPL"""
        print("╔═══════════════════════════════════════════╗")
        print("║   Code Assistant - Local AI on Pi 5      ║")
        print("╚═══════════════════════════════════════════╝")
        print("\nType your question or 'help' for commands\n")
        
        while True:
            try:
                # Get input
                user_input = input("\n>>> ").strip()
                
                if not user_input:
                    continue
                
                # Check if it's a command
                if user_input.startswith('/') or user_input.split()[0] in self.COMMANDS:
                    cmd = user_input[1:] if user_input.startswith('/') else user_input
                    should_continue = self.handle_command(cmd)
                    if not should_continue:
                        break
                else:
                    # Process as query
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
        self.state.context_files = files
        self.state.auto_context = not bool(files)  # Only auto if no files specified
        
        self.process_query(query)


def main():
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
  
  # Custom model
  %(prog)s --model ./models/deepseek-coder.gguf
        """
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='Files to include in context'
    )
    
    parser.add_argument(
        '-m', '--model',
        default='./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf',
        help='Path to GGUF model file'
    )
    
    parser.add_argument(
        '-q', '--query',
        help='Run single query and exit'
    )
    
    parser.add_argument(
        '-t', '--temperature',
        type=float,
        default=0.1,
        help='Model temperature (0.0-1.0, default: 0.1)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--llama-dir',
        default='./llama.cpp',
        help='Path to llama.cpp directory'
    )
    
    args = parser.parse_args()
    
    # Validate model exists
    if not Path(args.model).exists():
        print(f"Error: Model not found: {args.model}", file=sys.stderr)
        print("\nDownload a model first:", file=sys.stderr)
        print("  mkdir -p models", file=sys.stderr)
        print("  cd models", file=sys.stderr)
        print("  wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf", file=sys.stderr)
        sys.exit(1)
    
    # Create app
    try:
        app = CodeAssistantCLI(
            model_path=args.model,
            llama_cpp_dir=args.llama_dir,
            temperature=args.temperature
        )
        app.state.verbose = args.verbose
        
    except Exception as e:
        print(f"Error initializing: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run mode
    if args.query:
        # One-shot mode
        app.one_shot_mode(args.query, args.files)
    else:
        # Interactive mode
        if args.files:
            app.state.context_files = args.files
            print(f"Loaded {len(args.files)} files into context")
        
        app.interactive_mode()


if __name__ == "__main__":
    main()
