# Raspberry Pi Code Assistant 🥧🤖

**A Claude Code / Gemini CLI-style coding assistant running entirely on your Raspberry Pi 5**

Local AI-powered code assistant with intelligent file context, conversation memory, and zero API costs. Built specifically for Raspberry Pi 5 with optimized performance.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Raspberry Pi 5](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Model: Qwen2.5-Coder](https://img.shields.io/badge/Model-Qwen2.5--Coder-blue)](https://huggingface.co/Qwen)

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
- **⚡ Optimized**: Tuned for Pi 5 (16GB) - ~5-10 tokens/second
- **🔧 Tool Integration**: Shell commands, git, file operations
- **🎯 Zero Cost**: Completely local, no API fees
- **🔒 Private**: Your code never leaves your Pi

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

- **Hardware**: Raspberry Pi 5 (8GB minimum, 16GB recommended)
- **OS**: Raspberry Pi OS 64-bit (Debian 12 Bookworm)
- **Storage**: ~20GB free space
- **Internet**: Only for initial setup (download model)

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
| `reset` | Reset conversation |
| `help` | Show all commands |
| `quit` | Exit |

## ⚡ Performance

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

```
User Query
    ↓
Context Manager (smart file chunking)
    ↓
Conversation Manager (history + prompt)
    ↓
llama.cpp (7B model, 4-bit quantized)
    ↓
Response Processing (code extraction)
    ↓
Output + Tool Execution
```

**Key Components:**

- `assistant.py` - Main CLI and REPL
- `context_manager.py` - Intelligent file handling
- `model_runner.py` - llama.cpp wrapper
- `setup.sh` - Automated installation

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
