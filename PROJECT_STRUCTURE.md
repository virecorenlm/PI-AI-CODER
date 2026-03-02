# Project Structure

```
pi-code-assistant/
│
├── Core Application
│   ├── assistant.py              # Main CLI application (entry point)
│   ├── context_manager.py        # Intelligent file chunking & context
│   ├── model_runner.py           # llama.cpp wrapper & conversation
│   └── run.sh                    # Launcher script (created by setup)
│
├── Setup & Configuration
│   ├── setup.sh                  # Automated installation
│   ├── config.example.yaml       # Example configuration
│   └── requirements.txt          # Python dependencies (if any)
│
├── Documentation
│   ├── README.md                 # Project overview (create this)
│   ├── QUICKSTART.md            # 5-minute setup guide
│   ├── DOCUMENTATION.md         # Comprehensive docs
│   └── EXAMPLES.md              # Usage examples (optional)
│
├── Dependencies (created by setup)
│   ├── llama.cpp/               # llama.cpp build
│   │   ├── main                 # Main executable
│   │   ├── quantize             # Quantization tool
│   │   └── ...
│   │
│   ├── models/                  # GGUF models
│   │   ├── qwen2.5-coder-7b-instruct-q4_k_m.gguf
│   │   └── ...
│   │
│   └── venv/                    # Python virtual environment
│       └── ...
│
└── Runtime (created during use)
    ├── .file_cache/             # Cached file chunks
    └── performance.log          # Performance logs (if enabled)
```

## File Descriptions

### Core Application Files

**assistant.py**
- Main CLI application
- Handles user interaction (REPL)
- Command processing
- File management
- Tool execution (shell, git, save)
- Lines: ~400

**context_manager.py**
- Smart file loading and chunking
- Semantic code parsing (Python, generic)
- Relevance scoring for context
- Token limit management
- File caching
- Lines: ~300

**model_runner.py**
- llama.cpp wrapper
- Prompt formatting (ChatML for Qwen)
- Conversation history management
- Response parsing & code extraction
- Streaming support (experimental)
- Lines: ~300

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

Potential improvements:
- [ ] YAML config file loading
- [ ] Multiple model support (switch on-the-fly)
- [ ] Embeddings for semantic file search
- [ ] Web UI (optional)
- [ ] IDE integration (VSCode extension)
- [ ] Collaborative mode (multi-user)
- [ ] Code execution sandboxing
- [ ] Automated testing generation
- [ ] Documentation generation
- [ ] Commit message generation
- [ ] Code review automation

## Testing

Currently no formal tests. To add:

```bash
tests/
├── test_context_manager.py
├── test_model_runner.py
├── test_assistant.py
└── test_integration.py
```

Run with:
```bash
python -m pytest tests/
```

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
