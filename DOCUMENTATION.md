# Pi Code Assistant

**Local AI coding assistant running on Raspberry Pi 5 with llama.cpp**

A Claude Code / Gemini CLI-style application that runs entirely locally on your Pi, with intelligent file context management, conversation memory, and code execution capabilities.

## Features

- 🤖 **Smart Context**: Automatic file discovery and relevance-based chunking
- 💬 **Conversational**: Multi-turn conversations with memory
- 📁 **File-Aware**: Read, analyze, and modify code across multiple files
- ⚡ **Optimized**: Tuned for Pi 5 (16GB) with 4-bit quantized models
- 🔧 **Tool Integration**: Execute shell commands, save code, git integration
- 🎯 **No Dependencies**: Self-contained, no API keys required

## Performance

**Raspberry Pi 5 (16GB)**
- Model: Qwen2.5-Coder-7B-Q4_K_M (4.5GB)
- Speed: ~5-10 tokens/second
- Context: Up to 4K tokens
- Memory: ~6GB in use during inference

## Installation

```bash
# 1. Download the project
git clone <your-repo> pi-code-assistant
cd pi-code-assistant

# 2. Run setup (takes ~20 minutes)
chmod +x setup.sh
./setup.sh

# 3. Test it
./run.sh -q "Write a function to calculate Fibonacci numbers"
```

### Manual Setup

If the automatic setup fails:

```bash
# Install dependencies
sudo apt install build-essential cmake git python3-pip wget

# Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make -j4 && cd ..

# Download model
mkdir models && cd models
wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
cd ..

# Create Python venv
python3 -m venv venv
source venv/bin/activate

# Make executable
chmod +x *.py
```

## Usage

### Interactive Mode (Recommended)

```bash
./run.sh
```

```
>>> Write a Python function to parse JSON files

[AI generates code...]

>>> save parser.py
✓ Saved to parser.py

>>> exec python parser.py test.json
[runs the code...]

>>> add *.py
✓ 5 files in context

>>> Refactor these files to use async/await
```

### One-Shot Mode

```bash
# Simple query
./run.sh -q "Explain quicksort algorithm"

# With context files
./run.sh main.py utils.py -q "Find bugs in this code"

# Multiple files with glob
./run.sh src/*.py -q "Add type hints to all functions"
```

### Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `add <pattern>` | Add files to context | `add *.py src/*.js` |
| `remove <pattern>` | Remove files | `remove test_*` |
| `files` | List context files | `files` |
| `clear` | Clear all context | `clear` |
| `auto` | Toggle auto file discovery | `auto` |
| `exec <cmd>` | Run shell command | `exec python test.py` |
| `save <file>` | Save last code block | `save output.py` |
| `diff` | Show git diff | `diff` |
| `reset` | Clear conversation | `reset` |
| `help` | Show help | `help` |
| `quit` | Exit | `quit` |

## Examples

### Example 1: Analyzing Existing Code

```bash
./run.sh

>>> add src/database.py src/models.py
✓ 2 files in context

>>> What are the potential SQL injection vulnerabilities?

[AI analyzes and reports findings...]

>>> Show me how to fix the user_login function

[AI provides secure code...]

>>> save src/database_fixed.py
✓ Saved to src/database_fixed.py
```

### Example 2: Building New Features

```bash
./run.sh

>>> I need a REST API endpoint that accepts JSON and validates it against a schema

[AI generates Flask/FastAPI code...]

>>> Add error handling and logging

[AI updates the code...]

>>> save api.py
```

### Example 3: Debugging

```bash
./run.sh

>>> exec python main.py
Traceback (most recent call last):
  File "main.py", line 42, in process_data
    result = json.loads(data)
json.decoder.JSONDecodeError: Expecting value: line 1 column 1

>>> add main.py
>>> Fix this JSON parsing error

[AI analyzes and suggests fix...]
```

### Example 4: Refactoring

```bash
./run.sh legacy/*.py

>>> These files use callbacks. Convert them to async/await

[AI refactors all files...]

>>> Show me a diff of the changes

[AI highlights changes...]
```

## Advanced Usage

### Custom Model

```bash
# Use different model
./run.sh --model ./models/deepseek-coder.gguf

# Adjust temperature (creativity)
./run.sh --temperature 0.3  # More creative
./run.sh --temperature 0.05 # More deterministic
```

### Verbose Mode

```bash
./run.sh -v

# Shows:
# - Auto-discovered files
# - Context size
# - Token counts
```

### Auto Context Discovery

The assistant automatically finds relevant files based on your query:

```bash
>>> Write unit tests for the authentication module

# Auto-discovers: auth.py, user.py, config.py
# Uses these for context without you specifying
```

Disable with: `auto` command

### Git Integration

```bash
>>> diff
# Shows current git changes

>>> What changed in my last commit?
# AI analyzes git diff

>>> Write a commit message for these changes
```

## Configuration

### Model Settings

Edit `assistant.py` to tune performance:

```python
config = ModelConfig(
    n_ctx=4096,          # Context window (lower = less memory)
    n_predict=2048,      # Max response tokens
    temperature=0.1,     # 0.0-1.0 (lower = more focused)
    threads=4,           # Use all Pi cores
    repeat_penalty=1.1,  # Reduce repetition
)
```

### Context Manager

Edit `context_manager.py`:

```python
MAX_CONTEXT_TOKENS = 3000    # Total context size
MAX_FILE_SIZE_KB = 500       # Skip large files
```

### System Prompt

Edit `model_runner.py` to customize behavior:

```python
self.system_prompt = """You are Claude Code...

[Customize personality, behavior, output format]
"""
```

## Troubleshooting

### Out of Memory

**Symptoms:** Swap thrashing, system freeze

**Solutions:**
```bash
# Use smaller model
./run.sh --model ./models/phi-3.5-mini.gguf

# Reduce context
# Edit context_manager.py: MAX_CONTEXT_TOKENS = 2000

# Close other apps
pkill chromium-browser

# Check memory
htop
```

### Slow Performance

**Normal speeds:**
- First query: 30-60 seconds (loading)
- Subsequent: 10-30 seconds (5-10 tok/s)

**If slower:**
```bash
# Check CPU throttling
vcgencmd measure_temp
# Should be < 80°C

# Check swap usage
free -h
# Swap should be minimal

# Reduce context
./run.sh --temperature 0.1  # Faster sampling
```

### Model Not Found

```bash
# Download manually
cd models

# Qwen2.5-Coder (recommended)
wget https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf

# DeepSeek-Coder (alternative)
wget https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf

# Phi-3.5 (fast, smaller)
wget https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf
```

### Python Import Errors

```bash
source venv/bin/activate
python3 -c "import sys; print(sys.path)"

# If modules not found, run from project dir
cd /path/to/pi-code-assistant
./run.sh
```

## Architecture

```
┌─────────────────────────────────────────┐
│           User Query                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      Context Manager                    │
│  • Auto file discovery                  │
│  • Semantic chunking                    │
│  • Relevance scoring                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      Conversation Manager               │
│  • History tracking                     │
│  • Prompt formatting                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      Model Runner (llama.cpp)           │
│  • Qwen2.5-Coder 7B Q4_K_M             │
│  • 4-bit quantization                   │
│  • ~5-10 tokens/sec on Pi 5            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      Response Processing                │
│  • Code extraction                      │
│  • Format cleanup                       │
│  • Tool execution                       │
└─────────────────────────────────────────┘
```

## Model Recommendations

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **Qwen2.5-Coder-7B** | 4.5GB | Medium | ⭐⭐⭐⭐⭐ | Best overall (recommended) |
| DeepSeek-Coder-6.7B | 4.3GB | Medium | ⭐⭐⭐⭐ | Good alternative |
| Phi-3.5-mini | 2.5GB | Fast | ⭐⭐⭐ | Quick responses |
| CodeLlama-7B | 4.5GB | Medium | ⭐⭐⭐⭐ | Python-focused |

**4-bit quantization (Q4_K_M) is required for Pi 5**

## Extending the Assistant

### Adding Tools

Edit `assistant.py`:

```python
def handle_command(self, cmd: str) -> bool:
    # Add your custom command
    if command == 'mycommand':
        # Your logic here
        pass
```

### Custom Prompts

Create prompt templates in `model_runner.py`:

```python
def format_code_review_prompt(self, code, context):
    return f"""Review this code for:
    - Security issues
    - Performance problems
    - Best practices
    
    Code:
    {code}
    
    Context:
    {context}
    """
```

### File Type Support

Add new chunking strategies in `context_manager.py`:

```python
def chunk_rust_file(self, content, filepath):
    # Custom Rust chunking
    pass
```

## Performance Tuning

### For Maximum Speed

```python
# model_runner.py
config = ModelConfig(
    n_ctx=2048,        # Smaller context
    n_predict=512,     # Shorter responses
    temperature=0.05,  # Greedy sampling
    threads=4,
)
```

### For Best Quality

```python
config = ModelConfig(
    n_ctx=4096,
    n_predict=2048,
    temperature=0.15,
    top_p=0.95,
    repeat_penalty=1.15,
)
```

### Memory-Constrained

```python
# context_manager.py
MAX_CONTEXT_TOKENS = 2000
MAX_FILE_SIZE_KB = 200
```

## FAQ

**Q: Can I run this on Pi 4?**
A: Technically yes with 8GB model, but it will be very slow. Pi 5 recommended.

**Q: Why not use the API?**
A: This is completely local. No API costs, no internet needed, full privacy.

**Q: Can I use other models?**
A: Yes! Any GGUF model. Just place in `models/` and specify with `--model`.

**Q: How do I update?**
A: `git pull` and re-run `./setup.sh` if needed.

**Q: Can multiple people use it?**
A: One instance at a time. llama.cpp loads model in memory.

**Q: Is this better than ChatGPT?**
A: Different trade-offs. This is local, private, and free. ChatGPT is faster and more capable.

## Credits

- **llama.cpp**: Georgi Gerganov and contributors
- **Qwen2.5-Coder**: Alibaba Cloud
- **Inspiration**: Claude Code (Anthropic), Gemini CLI (Google)

## License

MIT License - See LICENSE file

---

**Built for hackers who value local control and privacy** 🔒🥧
