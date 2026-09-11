# Project Structure

```
pi-code-assistant/
│
├── Core Application (entry points)
│   ├── assistant.py              # CLI entry point (REPL, one-shot, `tui` subcommand)
│   ├── context_manager.py        # Backward-compat shim -> pi_ai_coder.context
│   ├── model_runner.py           # Backward-compat shim -> pi_ai_coder.models
│   └── run.sh                    # Launcher script (created by setup)
│
├── pi_ai_coder/                  # Backend package (used by both CLI and TUI)
│   ├── config.py                 # YAML + env + CLI config loading, provider selection, host profiles
│   ├── context/
│   │   └── manager.py            # ContextManager/FileChunk (chunking, relevance scoring)
│   ├── models/
│   │   ├── base.py               # ModelProvider interface, Message, ModelConfig, ModelInfo, HealthStatus
│   │   ├── factory.py            # create_provider(config) -- the only provider-branching code
│   │   ├── llama_cpp_provider.py # LlamaCppProvider (real streaming, cancellation, model discovery)
│   │   ├── ollama_provider.py    # OllamaProvider (HTTP API, never spawns a process)
│   │   └── fake_provider.py      # FakeModelProvider (deterministic, no model needed)
│   ├── tools/
│   │   ├── base.py               # RiskLevel, ToolResult, safe path resolution
│   │   ├── shell.py              # ShellTool
│   │   ├── git.py                # GitTool (read-only status/diff/log)
│   │   ├── files.py              # FileTool (read/write/create/apply_patch/delete/move/list/find, project-boundary enforced)
│   │   └── search.py             # SearchTool (ripgrep, Python fallback)
│   ├── agent/                    # the coding agent
│   │   ├── protocol.py           # ToolCall/ToolResult/ParsedTurn -- provider-independent types
│   │   ├── events.py             # AgentEvent/AgentEventType
│   │   ├── parsing.py            # parse_tool_calls() -- the <tool_call> fallback protocol parser
│   │   ├── permissions.py        # classify_command(), TOOL_RISK -- READ/WRITE/EXECUTE/DESTRUCTIVE
│   │   ├── tools.py              # ToolRegistry -- wires tools/* into agent-callable tools
│   │   ├── prompt.py             # build_agent_system_prompt() -- tool list + protocol instructions
│   │   ├── display.py            # describe_tool_call(), LiveProseFilter (shared CLI/TUI rendering)
│   │   └── service.py            # AgentService -- the bounded inspect/edit/test/summarize loop
│   ├── core/
│   │   ├── events.py             # StreamEvent/EventType/AssistantStatus
│   │   ├── project.py            # resolve_project_root() -- app root vs. project root
│   │   ├── session.py            # SessionState + SessionStore (JSON persistence, project-scoped)
│   │   └── assistant_service.py  # AssistantService: plain chat + session/context management
│   └── tui/
│       ├── app.py                # PiAiCoderApp (Textual)
│       ├── widgets/               # ProjectTree, ConversationView, PromptComposer, ...
│       └── screens/               # PreviewScreen, HelpScreen, CommandInputScreen, ApprovalScreen
│
├── tests/                        # pytest suite (no real model required)
│
├── Setup & Configuration
│   ├── setup.sh                  # Automated installation
│   ├── config.example.yaml       # Example configuration (copy to config.yaml)
│   └── pyproject.toml            # Package metadata, deps, `pi-coder` console script
│
├── Documentation
│   ├── README.md                 # Project overview
│   ├── QUICKSTART.md            # 5-minute setup guide
│   ├── DOCUMENTATION.md         # Comprehensive docs
│   └── PROJECT_STRUCTURE.md     # This file
│
├── Dependencies (created by setup)
│   ├── llama.cpp/               # llama.cpp build
│   │   ├── llama-cli / main     # CLI executable (either name is detected)
│   │   └── ...
│   │
│   ├── models/                  # GGUF models
│   │   └── qwen2.5-coder-7b-instruct-q4_k_m.gguf
│   │
│   └── venv/ or .venv/          # Python virtual environment
│
└── Runtime (created during use, gitignored)
    └── .pi-ai-coder/
        └── session.json          # Persisted context files, recent prompts, conversation
```

## File Descriptions

### Core Application Files

**assistant.py**
- CLI entry point: REPL, one-shot queries, and the `tui` subcommand
- Command processing (`add`/`remove`/`files`/`exec`/`save`/`diff`/... )
- Delegates all real work to `pi_ai_coder` (context, model, tools)

**context_manager.py** / **model_runner.py**
- Backward-compatible shims. The real implementations now live in
  `pi_ai_coder/context/manager.py` and `pi_ai_coder/models/`
  (`llama_cpp_provider.py`, `fake_provider.py`); these two files just
  re-export/adapt them so old imports keep working.

**pi_ai_coder/context/manager.py**
- Smart file loading and chunking (unchanged behavior from the original)
- Semantic code parsing (Python, generic)
- Relevance scoring for context
- Token limit management, file caching

**pi_ai_coder/models/**
- `base.py`: the `ModelProvider` interface (`chat`, `stream_chat`, `cancel`, `health_check`, `list_models`, `set_model`) all backends implement
- `factory.py`: `create_provider(config, fake_model=...)` -- the *only* place that branches on which backend is active
- `llama_cpp_provider.py`: llama.cpp wrapper -- ChatML prompt formatting, real token streaming, clean cancellation, detects either the `llama-cli` or `main` executable name, scans the model's directory (not the whole filesystem) for other GGUF files
- `ollama_provider.py`: talks to an already-running Ollama server over HTTP (`/api/chat`, `/api/tags`) -- never shells out to `ollama` or starts a server process
- `fake_provider.py`: deterministic streaming backend used by `--fake-model` and the test suite

**pi_ai_coder/tools/**
- `shell.py` (`ShellTool`), `git.py` (`GitTool`, read-only), `files.py` (`FileTool`, path-boundary enforced), `search.py` (`SearchTool`, ripgrep + Python fallback)
- `base.py`: shared `RiskLevel` (READ/WRITE/EXECUTE/DESTRUCTIVE) and `ToolResult`
- `FileTool` covers read/write/create_file/apply_patch/delete_file/move_file/list_directory/find_files/read_file_range -- every method resolves and validates the path stays inside the project root first

**pi_ai_coder/agent/** -- the coding agent (see `CLAUDE.md`'s Agent Architecture section)
- `protocol.py`: `ToolCall`/`ToolResult`/`ParsedTurn` -- the internal, provider-independent representation the loop operates on
- `parsing.py`: `parse_tool_calls()` -- strictly parses the `<tool_call>{...}</tool_call>` fallback protocol; malformed blocks are reported as errors, never executed or silently dropped
- `permissions.py`: `classify_command()` (pattern-based EXECUTE vs. DESTRUCTIVE for shell commands) and `TOOL_RISK` (static risk per tool)
- `tools.py`: `ToolRegistry` -- registers all agent tools (read_file, read_file_range, list_directory, find_files, search_code, git_status, git_diff, write_file, create_file, apply_patch, delete_file, move_file, run_command, run_tests), dispatching to the `pi_ai_coder/tools/` instances with argument validation and output capping
- `prompt.py`: builds the agent's system prompt from the registered tool list
- `display.py`: `describe_tool_call()` and `LiveProseFilter` (suppresses raw `<tool_call>` JSON from live-streamed output) -- shared by the CLI and TUI so agent actions render consistently
- `service.py`: `AgentService.run_task()` -- the bounded loop (`max_iterations`, `max_tool_calls`), yielding `AgentEvent`s; takes an `approve` callback for DESTRUCTIVE tool calls

**pi_ai_coder/core/**
- `assistant_service.py`: `AssistantService` -- plain one-shot/streaming chat (used directly for `--no-agent`, and for session/context management -- add/remove/clear context files, reset -- shared with the agent)
- `project.py`: `resolve_project_root()` -- the one canonical project/workspace root, validated to exist and be a directory; the CLI and TUI both resolve it once and pass it into every project-oriented component (never scattered `Path.cwd()` calls)
- `session.py`: `SessionState`/`SessionStore` -- JSON persistence under `<project_root>/.pi-ai-coder/`, so two projects never share session state
- `events.py`: the `StreamEvent`/`EventType`/`AssistantStatus` vocabulary used to stream activity to a UI

**pi_ai_coder/tui/**
- `app.py`: the Textual `PiAiCoderApp` -- prompt submission runs `AgentService.run_task()` in a worker thread, cross-thread `ApprovalScreen` blocking for DESTRUCTIVE calls
- `widgets/`: `ProjectTree`, `ConversationView` (now with `add_tool_action`/`add_tool_output` for agent steps), `PromptComposer`, `ContextPanel`, `ToolOutput`, `GitPanel`, `StatusBar`
- `screens/`: `PreviewScreen` (read-only file preview), `HelpScreen`, `CommandInputScreen` (modal text input), `ApprovalScreen` (modal y/n for destructive tool calls)

### Setup Files

**setup.sh**
- System dependency installation
- llama.cpp build
- Swap configuration
- Model download
- Validation & testing
- Lines: ~250

**config.example.yaml**
- Example configuration
- All tunable parameters
- Documentation via comments
- Lines: ~80

### Documentation Files

**QUICKSTART.md**
- Minimal setup instructions
- First run guide
- Common commands
- Emergency troubleshooting
- Lines: ~150

**DOCUMENTATION.md**
- Complete usage guide
- All features & commands
- Examples
- Architecture overview
- Advanced configuration
- Performance tuning
- FAQ
- Lines: ~800

## Key Design Decisions

### 1. No Heavy Dependencies
- Pure Python stdlib where possible
- Only subprocess for llama.cpp
- No ML frameworks (PyTorch, TensorFlow, etc.)
- No web frameworks
- Keeps it lightweight and portable

### 2. Modular Architecture
- Each file has single responsibility
- Easy to extend or replace components
- Clear interfaces between modules

### 3. Context Window Optimization
- Semantic chunking (not naive full-file reads)
- Relevance scoring to prioritize important code
- Token counting to stay within limits
- Caching to avoid re-parsing

### 4. Pi 5 Optimizations
- 4-thread utilization (Pi 5's 4 cores)
- Swap configuration in setup
- Memory-aware context sizing
- 4-bit quantized models only

### 5. User Experience
- Interactive REPL with commands
- One-shot mode for scripts
- Auto file discovery (smart defaults)
- Helpful error messages
- Progress indicators

## Data Flow

```
User Input
    ↓
Command Parser (assistant.py)
    ↓
    ├─→ Command? → Execute & Return
    │
    └─→ Query
        ↓
    File Discovery (auto or manual)
        ↓
    Context Builder (context_manager.py)
        ├─→ Load files
        ├─→ Chunk semantically
        ├─→ Score relevance
        └─→ Build optimized context
            ↓
    Conversation Manager (model_runner.py)
        ├─→ Add to history
        ├─→ Format prompt (ChatML)
        └─→ Build full prompt
            ↓
    llama.cpp Execution
        ├─→ Load model (first time)
        ├─→ Process prompt
        └─→ Generate tokens
            ↓
    Response Processing
        ├─→ Clean formatting
        ├─→ Extract code blocks
        └─→ Update history
            ↓
    Display to User
```

## Extension Points

### Adding New Models
1. Download GGUF model to `models/`
2. Update prompt format in `model_runner.py` if needed
3. Adjust `ModelConfig` parameters
4. Run with `--model path/to/model.gguf`

### Adding New File Types
1. Add chunking function in `context_manager.py`
2. Update `load_file()` to detect file type
3. Test with your files

### Adding New Commands
1. Add to `COMMANDS` dict in `assistant.py`
2. Implement in `handle_command()`
3. Update help text

### Tool Integration
Examples of tools to add:
- Code formatter (black, prettier)
- Linter integration (pylint, eslint)
- Test runner
- Documentation generator
- Database query executor
- HTTP request tool

Add in `handle_command()` in `assistant.py`

## Performance Characteristics

### Memory Usage
- Base: ~2GB (OS + system)
- Model loading: +4-5GB (7B Q4_K_M)
- Context processing: +500MB-1GB
- **Total: ~6-8GB typical**

### CPU Usage
- Model inference: 100% of 4 cores
- First query: 30-60s (model load + inference)
- Subsequent: 10-30s (inference only)
- Idle: <1%

### Disk Usage
- llama.cpp: ~100MB
- Model: 4.5GB (Qwen2.5-Coder)
- Python + cache: <100MB
- **Total: ~5GB**

### Network Usage
- Setup: ~5GB (model download)
- Runtime: 0 (fully local)

## Future Enhancements

Done in this iteration:
- [x] YAML config file loading (`pi_ai_coder/config.py`)
- [x] Textual TUI workspace with streaming, context/git/tool panels
- [x] Fake model backend + test suite (no GGUF/llama.cpp required for tests)
- [x] Session persistence (`.pi-ai-coder/session.json`)
- [x] Multi-provider model backend: llama.cpp and Ollama behind one interface, chosen via config/`--provider`/host profile
- [x] Named host profiles (`config.yaml`'s `profiles:` section) for using one project directory from multiple machines
- [x] Model discovery (`models`/`model <name>` commands, "List models"/"Change model" in the TUI)
- [x] Canonical project/workspace root (`pi_ai_coder/core/project.py`), `--project` on both the CLI and `tui`, decoupled from PI-AI-CODER's own install directory
- [x] User-level config (`~/.config/pi-ai-coder/config.yaml`) so provider/profile setup persists across projects
- [x] A real bounded agent/tool loop (`pi_ai_coder/agent/`): search/read/edit (create/patch/write/delete/move)/run commands, iterate, summarize -- the default behavior for a plain query now, with `--no-agent` as the opt-out
- [x] A provider-independent tool-calling protocol (text-based `<tool_call>` fallback, works identically for llama.cpp, Ollama, and the fake provider)
- [x] Destructive-action approval gate (pattern-based shell command classification; CLI prompt / TUI modal)

Still potential improvements:
- [ ] In-place file editing in the preview pane (the agent's own tools are how edits happen today)
- [ ] Native provider tool-calling as an optional fast path alongside the text protocol
- [ ] A checkpoint/undo layer beyond bare git
- [ ] An OpenAI-compatible local-server provider
- [ ] Embeddings for semantic file search
- [ ] Web UI (optional)
- [ ] IDE integration (VSCode extension)
- [ ] Automated testing generation
- [ ] Commit message generation
- [ ] Code review automation

## Testing

```bash
tests/
├── test_config.py
├── test_context_manager.py
├── test_session.py
├── test_tools.py
├── test_fake_provider.py
├── test_llama_cpp_provider.py
├── test_ollama_provider.py     # HTTP calls mocked -- no server needed
├── test_factory.py
├── test_import_order.py        # guards against a circular-import regression
├── test_project_root.py        # app-root vs. project-root, launched via subprocess
├── test_assistant_service.py
├── test_agent_protocol.py      # <tool_call> parsing, malformed-call rejection
├── test_agent_permissions.py   # shell command risk classification
├── test_agent_tools.py         # ToolRegistry: path/symlink safety, apply_patch, search_code, run_command
├── test_agent_service.py       # the bounded loop: multi-step, limits, cancellation, approval
├── test_agent_cli.py           # agent wired into assistant.py, via real subprocess
├── test_agent_tui.py           # agent wired into the TUI, headless Pilot tests
└── test_tui_smoke.py           # headless Textual Pilot tests
```

Run with:
```bash
pip install pytest pytest-asyncio
pytest
```

None of these require a real GGUF model or llama.cpp build --
`FakeModelProvider` stands in for the model everywhere it's needed.

## Contributing

To contribute:
1. Fork the repo
2. Create feature branch
3. Test on Pi 5
4. Submit PR with description

Guidelines:
- Keep it lightweight (no heavy deps)
- Optimize for Pi 5 performance
- Document new features
- Provide examples

## License

MIT License - Feel free to use, modify, distribute

---

**This structure prioritizes simplicity, performance, and extensibility.**
