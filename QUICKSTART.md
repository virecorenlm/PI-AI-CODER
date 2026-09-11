# Quick Start (5 Minutes)

For people who just want it working NOW.

## Prerequisites

- Raspberry Pi 5 with 8GB+ RAM (16GB recommended)
- Raspbian/Raspberry Pi OS 64-bit
- ~20GB free storage
- Internet connection (for setup only)

## Installation

```bash
# 1. Get the code
git clone <repo-url> ~/code-assistant
cd ~/code-assistant

# 2. Run setup
chmod +x setup.sh
./setup.sh

# Answer the prompts:
# - Choose model: 1 (Qwen2.5-Coder - best for code)
# - Wait 15-20 minutes for download/build

# 3. Done!
```

## First Run

```bash
# Interactive mode
./run.sh

>>> Write a Python function to reverse a string

# One-shot mode
./run.sh -q "Write a hello world program in Rust"

# Full-screen TUI workspace (file tree, streaming chat, git, tool output)
./run.sh tui
```

## Common Commands

```bash
# With files
./run.sh main.py utils.py

# Different model
./run.sh --model models/other-model.gguf

# More creative
./run.sh --temperature 0.3

# Verbose
./run.sh -v
```

## Inside Interactive Mode

```
>>> add *.py              # Add Python files to context
>>> files                 # See what's loaded
>>> help                  # All commands
>>> quit                  # Exit
```

## Troubleshooting

**"Model not found"**
```bash
cd ~/code-assistant/models
wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

**"llama.cpp main not found"**
```bash
cd ~/code-assistant/llama.cpp
make clean && make -j4
```

**Out of memory**
```bash
# Use smaller model
./run.sh --model models/phi-3.5-mini.gguf

# Or edit context_manager.py:
# MAX_CONTEXT_TOKENS = 2000
```

**Too slow**
- First query takes 30-60s (normal, loading model)
- Expect 5-10 tokens/second on Pi 5
- Close other apps, check `htop`

## What You Get

- Local AI assistant (no API needed)
- Reads your code files
- Writes/debugs/explains code
- Executes shell commands
- Git integration
- Conversation memory
- Zero cost after setup

## Performance

**Pi 5 (16GB):**
- Qwen2.5-Coder-7B: ~6-8 tok/s
- First response: 30-60s
- Subsequent: 10-30s
- Memory: ~6GB during inference

**Pi 5 (8GB):**
- Use Phi-3.5-mini instead
- ~8-12 tok/s (faster, less capable)
- Memory: ~4GB

## Next Steps

Read `DOCUMENTATION.md` for:
- Advanced usage
- All commands
- Configuration
- Examples
- Troubleshooting

Or just start using it:
```bash
./run.sh
>>> Let's build something
```

---

**TL;DR:** Run `./setup.sh`, wait 20 min, run `./run.sh`, profit.
