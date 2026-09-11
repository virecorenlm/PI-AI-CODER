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
│   │   └── files.py              # FileTool (read/save, project-boundary enforced)
│   ├── core/
│   │   ├── events.py             # StreamEvent/EventType/AssistantStatus
│   │   ├── session.py            # SessionState + SessionStore (JSON persistence)
│   │   └── assistant_service.py  # AssistantService: ties it all together
│   └── tui/
│       ├── app.py                # PiAiCoderApp (Textual)
│       ├── widgets/               # ProjectTree, ConversationView, PromptComposer, ...
│       └── screens/               # PreviewScreen, HelpScreen, CommandInputScreen
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
- `shell.py` (`ShellTool`), `git.py` (`GitTool`, read-only), `files.py` (`FileTool`, path-boundary enforced)
- `base.py`: shared `RiskLevel` (READ/WRITE/EXECUTE/DESTRUCTIVE) and `ToolResult`

**pi_ai_coder/core/**
- `assistant_service.py`: `AssistantService` -- context resolution, message assembly, blocking/streaming chat
- `session.py`: `SessionState`/`SessionStore` -- JSON persistence under `.pi-ai-coder/`
- `events.py`: the `StreamEvent`/`EventType`/`AssistantStatus` vocabulary used to stream activity to a UI

**pi_ai_coder/tui/**
- `app.py`: the Textual `PiAiCoderApp`
- `widgets/`: `ProjectTree`, `ConversationView`, `PromptComposer`, `ContextPanel`, `ToolOutput`, `GitPanel`, `StatusBar`
- `screens/`: `PreviewScreen` (read-only file preview), `HelpScreen`, `CommandInputScreen` (modal text input)

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

Still potential improvements:
- [ ] In-place file editing (preview is currently read-only)
- [ ] Model-requested tool calls behind a real permission/approval system
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
├── test_assistant_service.py
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
