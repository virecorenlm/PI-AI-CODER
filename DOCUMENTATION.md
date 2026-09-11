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

# Install Python dependencies (needed for the TUI: Textual + Rich + PyYAML)
pip install textual rich pyyaml
# for running the test suite too:
pip install pytest pytest-asyncio

# Make executable
chmod +x *.py
```

`setup.sh` installs these automatically; the manual steps above are only
needed if you're not using it.

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
| `models` | List models for the current provider | `models` |
| `model [name]` | Show/switch the active model | `model qwen3.5:latest` |
| `reset` | Clear conversation | `reset` |
| `help` | Show help | `help` |
| `quit` | Exit | `quit` |

## Model Providers

PI-AI-CODER supports two model backends behind one `ModelProvider`
interface (`pi_ai_coder/models/base.py`); `pi_ai_coder/models/factory.py`
is the only place that picks between them, based on `model.provider` in
config, a `--provider` flag, or a host profile.

### llama.cpp (default)

Runs a llama.cpp subprocess against a local GGUF file. Good for a
Raspberry Pi, any CPU-only box, or when you want direct control over
llama.cpp's own parameters.

```bash
./run.sh --provider llama_cpp --model ./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

`list_models` (the `models` command) scans the *directory containing your
configured model* for other `*.gguf` files -- it never scans the whole
filesystem. `model <name-or-path>` switches to another file in that
directory (or any explicit path).

### Ollama

Talks to an already-running Ollama server over its HTTP API
(`http://127.0.0.1:11434` by default). PI-AI-CODER never starts or manages
an Ollama process -- start it yourself (`ollama serve`, or as a systemd
service) before using this provider. Good for workstations with more
RAM/a GPU and models already pulled via `ollama pull`.

```bash
./run.sh --provider ollama --ollama-model qwen3.5:latest --ollama-host http://127.0.0.1:11434
```

`models`/`model <name>` list/switch among models Ollama already has
installed (via its `/api/tags` endpoint) -- PI-AI-CODER doesn't pull new
models for you.

If the server isn't reachable, both the CLI and the TUI print a
non-fatal warning (`ollama serve` reminder included) at startup rather
than crashing -- you can still use `models`/`model`/other commands, but a
chat request will fail until the server is up.

### Choosing a provider

```bash
--provider llama_cpp   # or: --provider ollama
```
or in `config.yaml`:
```yaml
model:
  provider: ollama
```
or via a named profile (see Configuration below):
```bash
./run.sh --profile asrock
```

## TUI Workspace

Alongside the REPL, PI-AI-CODER now has a full-screen Textual workspace:

```bash
./run.sh tui              # or: python assistant.py tui
./run.sh tui --fake-model # try the UI without llama.cpp/a GGUF model
```

The workspace shows a project file tree, the conversation with streaming
responses, a context panel, a git status pane, and a tool output pane for
shell commands -- all built on the same backend as the REPL (see
[Architecture](#architecture)), so context selection, model config, and
tool execution behave identically in both.

Key shortcuts (also see the in-app help screen, `F1`):

| Key | Action |
|-----|--------|
| `ctrl+p` | Command palette |
| `ctrl+o` | Focus project tree |
| `ctrl+l` | Focus prompt composer |
| `ctrl+g` | Focus git panel |
| `ctrl+t` | Focus tool output |
| `ctrl+r` | Reset conversation |
| `ctrl+k` | Clear manual context |
| `ctrl+j` | Submit prompt (most terminals send this for Ctrl+Enter) |
| `ctrl+c` | Cancel generation |
| `ctrl+q` | Quit |
| `a` / `d` (in tree or preview) | Add / remove file from context |

Limitations in this iteration: file preview is read-only (no in-place
editing yet), and the model cannot request tools itself -- every shell,
git, and file action is user-initiated by design (see `CLAUDE.md`'s
Tool Permissions section).

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

Configuration now loads from a real YAML file, following this precedence
(lowest to highest):

```
built-in defaults  <  config file  <  selected host profile  <  environment variables  <  CLI arguments
```

Copy `config.example.yaml` to `config.yaml` in your project directory to
customize it -- the app runs fine without one, using the same defaults as
before. Both the CLI and the TUI load the same config via
`pi_ai_coder.config.load_config()`.

```yaml
model:
  provider: llama_cpp   # or: ollama
  path: "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
  context_size: 4096
  max_tokens: 2048
  temperature: 0.1
  threads: 4

ollama:
  host: "http://127.0.0.1:11434"
  model: "qwen3.5:latest"

project:
  auto_context: true
  max_file_size_kb: 500

ui:
  theme: dark
```

Environment variable overrides (e.g. for containers/systemd units) use a
`PI_CODER_<SECTION>_<FIELD>` naming scheme, such as
`PI_CODER_MODEL_TEMPERATURE=0.3`, `PI_CODER_MODEL_PROVIDER=ollama`, or
`PI_CODER_OLLAMA_HOST=http://192.168.1.50:11434`.

`-m/--model`, `-t/--temperature`, `--llama-dir`, `--provider`,
`--ollama-host`, `--ollama-model` on the CLI (and the equivalents on `tui`)
still override everything, same as before.

### Host Profiles

A `profiles:` section in `config.yaml` bundles settings for a named
machine, so the same project directory works from more than one host
without editing config each time:

```yaml
profiles:
  pi5:
    provider: llama_cpp
    threads: 4
    context_size: 4096

  asrock:
    provider: ollama
    ollama_host: "http://127.0.0.1:11434"
    model: "qwen3.5:latest"
```

Select one with `--profile <name>`, the `PI_CODER_PROFILE` env var, or a
top-level `profile: <name>` key in `config.yaml`. A profile's settings
apply after the file's generic `model:`/`ollama:` sections but before
environment variables and CLI flags -- so `--profile asrock -t 0.3` still
lets the CLI flag win. Profile keys are flat (not nested under
`model:`/`ollama:`); the `model` key means an Ollama tag when that
profile's `provider` is `ollama`, otherwise a llama.cpp GGUF path.
Profiles are optional -- nothing requires you to define any.

### System Prompt

The system prompt lives in `pi_ai_coder/core/assistant_service.py`
(`DEFAULT_SYSTEM_PROMPT`) and is shared by the CLI and the TUI.

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

The CLI (`assistant.py`) and the Textual TUI (`pi_ai_coder.tui`) are both
thin front-ends over one backend, `pi_ai_coder`:

```
              CLI (assistant.py)      TUI (pi_ai_coder.tui.app)
                        \                    /
                         v                  v
                    AssistantService (pi_ai_coder.core)
                     |         |          |          |
                     v         v          v          v
              ContextManager  ModelProvider   Tools    SessionState
              (context/)      (models/)      (tools/)  (core/session.py)
                                  |              |
                           factory.py        ShellTool
                          create_provider()  GitTool
                            |    |    |      FileTool
                            v    v    v
                    LlamaCppProvider  OllamaProvider  FakeModelProvider
```

- **`ModelProvider`** (`pi_ai_coder/models/base.py`) is the swappable model
  interface -- `LlamaCppProvider` wraps llama.cpp (ChatML prompts, real
  token streaming, clean cancellation, and it looks for either `llama-cli`
  or the older `main` binary name). `OllamaProvider` talks to an
  already-running Ollama server over HTTP (never starts one itself).
  `FakeModelProvider` streams a deterministic canned response so the UI
  and tests don't need a real model. `pi_ai_coder/models/factory.py`
  (`create_provider(config, fake_model=...)`) is the one place that picks
  a concrete provider based on `config.model.provider` -- the CLI and TUI
  never branch on which backend is active.
- **`ContextManager`** (`pi_ai_coder/context/manager.py`) is unchanged in
  behavior from the original `context_manager.py`: ignore patterns,
  Python-aware chunking, Jaccard relevance scoring, char-budget context
  assembly.
- **Tools** (`pi_ai_coder/tools/`) wrap shell execution, git status/diff,
  and file read/write behind a `RiskLevel` (`READ`/`WRITE`/`EXECUTE`/
  `DESTRUCTIVE`) so a future permission layer has something to check
  against. File writes validate the target path stays inside the project
  root.
- **`SessionState`/`SessionStore`** (`pi_ai_coder/core/session.py`)
  persist context files, recent prompts, and recent conversation turns as
  JSON under `.pi-ai-coder/` in the project (gitignored automatically).
  The CLI stays ephemeral (no behavior change); the TUI restores state on
  restart.

`context_manager.py` and `model_runner.py` at the repo root still exist as
backward-compatible shims re-exporting/wrapping the new package, in case
anything imports them directly.

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
