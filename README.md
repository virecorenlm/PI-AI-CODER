# PI-AI-CODER 🥧🤖

**A Claude Code / Gemini CLI-style local coding assistant -- from a Raspberry Pi 5 to a full Linux workstation**

Local AI-powered code assistant with intelligent file context, conversation memory, and zero API costs. Runs on llama.cpp (GGUF models, great for a Pi) or Ollama (great on a workstation with more RAM/GPU) through the same interface.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-red)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Providers: llama.cpp | Ollama](https://img.shields.io/badge/Providers-llama.cpp%20%7C%20Ollama-blue)](#-model-providers)

## 🚀 Quick Start

```bash
# Clone and setup (takes ~20 minutes)
git clone <repo-url> ~/code-assistant
cd ~/code-assistant
chmod +x setup.sh
./setup.sh

# Run it
./run.sh
>>> Write a Python function to parse CSV files
```

**That's it.** No API keys, no cloud services, no subscriptions.

## ✨ Features

- **🤖 Smart AI Assistant**: Qwen2.5-Coder 7B model optimized for code
- **📁 File-Aware**: Automatically reads and understands your codebase
- **💬 Conversational**: Multi-turn conversations with memory
- **⚡ Optimized**: Tuned per host via config -- ~5-10 tokens/second on a Pi 5, much faster on a workstation
- **🔌 Pluggable Model Backends**: llama.cpp or Ollama, chosen by config/CLI flag, no code changes
- **🔧 Tool Integration**: Shell commands, git, file operations
- **🖥️ Full-Screen TUI**: A Textual workspace with a file tree, streaming
  chat, context panel, git status, and tool output (`./run.sh tui`)
- **🎯 Zero Cost**: Completely local, no API fees
- **🔒 Private**: Your code never leaves your machine

## 🔌 Model Providers

PI-AI-CODER talks to models through one interface and supports two backends:

```bash
# llama.cpp (default) -- GGUF models, good for a Pi or any CPU-only box
./run.sh --provider llama_cpp --model ./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf

# Ollama -- point at an already-running server (never started for you)
./run.sh --provider ollama --ollama-model qwen3.5:latest

# Named host profile from config.yaml (see config.example.yaml)
./run.sh --profile asrock
```

Or set it once in `config.yaml`:

```yaml
model:
  provider: ollama   # or llama_cpp
ollama:
  host: "http://127.0.0.1:11434"
  model: "qwen3.5:latest"
```

Inside the REPL/TUI, `models` lists what's available and `model <name>`
switches models within the current provider.

## 🖥️ TUI Workspace

```bash
./run.sh tui                # full-screen workspace
./run.sh tui --fake-model   # try it without llama.cpp/a GGUF model
```

Project tree on the left, streaming conversation and prompt composer on
the right, git status and tool output along the bottom. `Ctrl+P` opens
the command palette; `F1` shows all keyboard shortcuts. See
[DOCUMENTATION.md](DOCUMENTATION.md#tui-workspace) for the full shortcut
list and current limitations.

## 📊 What You Get

```
┌─────────────────────────────────────────────┐
│  Interactive coding assistant on your Pi    │
│  • Reads your files intelligently           │
│  • Writes/debugs/explains code              │
│  • Executes commands                        │
│  • Remembers conversation                   │
│  • Works offline                            │
└─────────────────────────────────────────────┘
```

## 🎯 Use Cases

### Code Analysis
```bash
./run.sh src/*.py
>>> Find potential security vulnerabilities
>>> Suggest performance improvements
>>> Explain this complex function
```

### Code Generation
```bash
./run.sh
>>> Write a REST API with authentication
>>> Create unit tests for my parser module
>>> Generate documentation from this code
```

### Debugging
```bash
./run.sh
>>> exec python main.py
[error output]
>>> Fix this JSON parsing error
>>> Add proper error handling
```

### Refactoring
```bash
./run.sh legacy/*.py
>>> Convert these to use async/await
>>> Add type hints
>>> Modernize to Python 3.12
```

## 📋 Requirements

- **Hardware**: Raspberry Pi 5 (8GB minimum, 16GB recommended) *or* any 64-bit
  Linux workstation -- more RAM/CPU/GPU just means faster inference
- **OS**: 64-bit Linux (Raspberry Pi OS, Ubuntu, Debian, ...)
- **Model backend**: either a local llama.cpp build + GGUF model, or an
  already-running [Ollama](https://ollama.com) server
- **Storage**: ~20GB free space (for a llama.cpp GGUF model; not needed if
  using Ollama, which manages its own model storage)
- **Internet**: Only for initial setup (downloading llama.cpp/a model, or `ollama pull`)

## 🔧 Installation

### Automatic Setup (Recommended)

```bash
cd ~/code-assistant
chmod +x setup.sh
./setup.sh
```

The script will:
1. Install system dependencies
2. Configure swap memory
3. Build llama.cpp
4. Download AI model (~4.5GB)
5. Set up Python environment
6. Validate installation

**Time: ~20 minutes** (mostly downloading model)

### Manual Setup

<details>
<summary>Click to expand manual setup instructions</summary>

```bash
# System dependencies
sudo apt update
sudo apt install -y build-essential cmake git python3-pip wget

# Configure swap
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=8192/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make -j4
cd ..

# Download model
mkdir -p models && cd models
wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
cd ..

# Python environment
python3 -m venv venv
source venv/bin/activate

# Make executable
chmod +x *.py *.sh
```
</details>

## 🎮 Usage

### Interactive Mode (Recommended)

```bash
./run.sh
```

```
>>> add *.py                    # Add files to context
>>> files                       # See what's loaded
>>> Write unit tests            # AI generates tests
>>> save test_module.py         # Save the code
>>> exec pytest test_module.py  # Run tests
>>> reset                       # Clear conversation
>>> quit                        # Exit
```

### One-Shot Mode

```bash
# Simple query
./run.sh -q "Explain quicksort algorithm"

# With context files
./run.sh main.py utils.py -q "Refactor this code"

# Multiple files
./run.sh src/*.py -q "Add type hints"
```

### Advanced Options

```bash
# Use different model
./run.sh --model models/deepseek-coder.gguf

# Adjust creativity
./run.sh --temperature 0.3  # More creative
./run.sh --temperature 0.05 # More deterministic

# Verbose mode
./run.sh -v  # Shows context size, timing

# Help
./run.sh --help
```

## 🧪 Development

```bash
pip install pytest pytest-asyncio  # test deps
pytest                              # backend + TUI smoke tests (no model needed)
./run.sh tui --fake-model           # try the TUI without llama.cpp/a GGUF model
python -m compileall .              # quick syntax check
```

## 📚 Commands Reference

| Command | Description |
|---------|-------------|
| `add <pattern>` | Add files to context |
| `remove <pattern>` | Remove files from context |
| `files` | List current context files |
| `clear` | Clear all context |
| `auto` | Toggle auto file discovery |
| `exec <cmd>` | Execute shell command |
| `save <file>` | Save last code block |
| `diff` | Show git diff |
| `models` | List models available for the current provider |
| `model [name]` | Show, or switch to, the active model |
| `reset` | Reset conversation |
| `help` | Show all commands |
| `quit` | Exit |

## ⚡ Performance

Performance depends entirely on the host and provider you choose --
tune `threads`/`context_size` in `config.yaml` (or a profile) per machine.

### Raspberry Pi 5 (16GB)

- **Model**: Qwen2.5-Coder-7B Q4_K_M (4.5GB)
- **Speed**: 5-10 tokens/second
- **Memory**: ~6GB during inference
- **First query**: 30-60 seconds (includes loading)
- **Subsequent**: 10-30 seconds

### Raspberry Pi 5 (8GB)

Use Phi-3.5-mini instead:
```bash
./run.sh --model models/phi-3.5-mini.gguf
```
- Faster (8-12 tok/s) but less capable

## 🔬 Architecture

The CLI and the TUI are both thin front-ends over one backend package,
`pi_ai_coder`, so context selection, model execution, and tool behavior
are identical in both:

```
assistant.py (CLI)      pi_ai_coder.tui (Textual UI)
        \                     /
         AssistantService (pi_ai_coder.core)
          |        |        |         |
     ContextManager  ModelProvider  Tools  SessionState
          |         (via factory.py)     (shell/git/file)
          |               |
          |      LlamaCppProvider / OllamaProvider / FakeModelProvider
```

**Key Components:**

- `assistant.py` - CLI entry point (REPL + one-shot + `tui` subcommand)
- `pi_ai_coder/context/` - Intelligent file handling (moved from `context_manager.py`)
- `pi_ai_coder/models/` - `ModelProvider` interface, `factory.py` (the only place that picks a backend), `LlamaCppProvider`, `OllamaProvider`, `FakeModelProvider`
- `pi_ai_coder/tools/` - `ShellTool`, `GitTool`, `FileTool` with path-safety checks
- `pi_ai_coder/core/` - `AssistantService`, session persistence, streaming events
- `pi_ai_coder/tui/` - the Textual workspace
- `setup.sh` - Automated installation

`context_manager.py` and `model_runner.py` remain at the repo root as
backward-compatible shims, in case anything still imports them directly.
See [DOCUMENTATION.md](DOCUMENTATION.md#architecture) for the full picture.

## 🎯 Recommended Models

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| **Qwen2.5-Coder-7B** ⭐ | 4.5GB | Medium | Excellent | General coding |
| DeepSeek-Coder-6.7B | 4.3GB | Medium | Very Good | Alternative |
| Phi-3.5-mini | 2.5GB | Fast | Good | 8GB Pi or speed |
| CodeLlama-7B | 4.5GB | Medium | Very Good | Python focus |

All use 4-bit quantization (Q4_K_M) - required for Pi 5.

## 🐛 Troubleshooting

<details>
<summary><b>Out of Memory</b></summary>

```bash
# Use smaller model
./run.sh --model models/phi-3.5-mini.gguf

# Close other apps
pkill chromium-browser

# Check memory
htop
```
</details>

<details>
<summary><b>Slow Performance</b></summary>

First query is always slowest (30-60s) - this is normal (model loading).

If consistently slow:
```bash
# Check temperature
vcgencmd measure_temp  # Should be < 80°C

# Check swap
free -h  # Swap should be minimal

# Reduce context
# Edit context_manager.py: MAX_CONTEXT_TOKENS = 2000
```
</details>

<details>
<summary><b>Model Not Found</b></summary>

```bash
cd models
wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```
</details>

<details>
<summary><b>llama.cpp Build Failed</b></summary>

```bash
cd llama.cpp
make clean
make -j4

# Check build
./main --version
```
</details>

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Complete guide
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Architecture details
- **[config.example.yaml](config.example.yaml)** - Configuration options

## 💡 Examples

### Example 1: Code Review

```bash
./run.sh

>>> add src/auth.py src/database.py
✓ 2 files in context

>>> Review this authentication code for security issues

[AI analyzes and reports findings...]

>>> Show me how to fix the SQL injection vulnerability

[AI provides secure code...]

>>> save src/auth_fixed.py
✓ Saved
```

### Example 2: New Feature

```bash
./run.sh

>>> Create a rate limiter decorator for Flask routes

[AI generates code...]

>>> Add Redis support

[AI updates code...]

>>> save rate_limiter.py
```

### Example 3: Debugging

```bash
./run.sh main.py

>>> exec python main.py
[error trace]

>>> Fix this JSON error and add proper error handling

[AI provides fix...]
```

## 🔄 Updates

```bash
cd ~/code-assistant
git pull
./setup.sh  # If needed
```

## 🤝 Contributing

Contributions welcome! Guidelines:

- Keep dependencies minimal
- Optimize for Pi 5 performance
- Document new features
- Test on actual Pi hardware

## 📝 License

MIT License - See [LICENSE](LICENSE) file

## 🙏 Credits

- **llama.cpp**: Georgi Gerganov and contributors
- **Qwen2.5-Coder**: Alibaba Cloud
- **Inspiration**: Claude Code (Anthropic), Gemini CLI (Google)

## 🌟 Star History

If this helped you, star the repo!

---

**Built by hackers, for hackers who value local control and privacy** 🔒

**Questions?** Open an issue
**Want to chat?** Join discussions

---

### Why This Exists

Because:
- API costs add up
- Internet isn't always available  
- Code should stay on your machine
- You should own your tools
- Pi 5 is powerful enough
- Local AI is the future

**Happy coding! 🚀**
