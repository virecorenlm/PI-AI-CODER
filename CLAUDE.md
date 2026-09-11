# CLAUDE.md

## Project

PI-AI-CODER is a local-first coding assistant designed to run on multiple Linux hosts -- from a Raspberry Pi 5 with 16 GB RAM to a full Ubuntu workstation. Hardware assumptions and model-backend choices are configuration-driven (see `pi_ai_coder/config.py` and `config.example.yaml`'s `profiles:` section), not hard-coded into the application core.

The long-term goal is to build a genuine local coding workspace comparable in spirit to Claude Code, Codex CLI, OpenCode, and similar coding agents, while keeping the system lightweight, private, inspectable, and usable offline.

This repository already contains working functionality. Treat it as an existing application that must be evolved carefully, not as a greenfield rewrite.

---

# Current Architecture

The important existing components are:

* `assistant.py`

  * Current CLI / REPL entry point
  * User command handling
  * Context-file selection
  * Shell execution
  * Git diff
  * Saving generated code
  * Query dispatch

* `context_manager.py`

  * File loading
  * File filtering
  * File chunking
  * Relevance scoring
  * Context-size management
  * Context caching

* `model_runner.py`

  * llama.cpp integration
  * Model configuration
  * Prompt formatting
  * Conversation history
  * Code-block extraction
  * Blocking inference
  * Experimental streaming inference

* `setup.sh`

  * Raspberry Pi setup
  * llama.cpp build/setup
  * Model setup
  * Environment configuration

* `config.example.yaml`

  * Intended application configuration

* `README.md`

* `QUICKSTART.md`

* `DOCUMENTATION.md`

* `PROJECT_STRUCTURE.md`

Always inspect these files before making architectural changes.

---

# Core Development Principle

Do not replace working PI-AI-CODER functionality simply because a cleaner implementation is possible.

Prefer:

1. Understand existing behavior.
2. Extract reusable functionality.
3. Preserve compatibility.
4. Improve interfaces.
5. Add new capabilities incrementally.

Avoid unnecessary rewrites.

The project should remain runnable throughout development whenever practical.

---

# Target Architecture

The application is moving toward this conceptual structure:

```text
User Interface
    |
    v
Application / Assistant Service
    |
    +--> Model Provider
    |
    +--> Context Manager
    |
    +--> File Tools
    |
    +--> Shell Tools
    |
    +--> Git Tools
    |
    +--> Session State
```

UI code must not directly contain model, Git, shell, or context-management implementation.

The backend should eventually support multiple frontends:

* existing CLI
* Textual TUI
* future desktop GUI
* future web interface
* future remote client

Design accordingly.

---

# UI Direction

The primary interactive interface should be a Python Textual TUI.

Do not introduce Electron for the main Pi interface.

The application should remain comfortable to use:

* locally
* in a Linux terminal
* over SSH
* on Raspberry Pi hardware

The TUI should eventually include:

* project file tree
* AI conversation
* streaming model responses
* prompt composer
* context-file management
* tool output
* Git status
* Git diff
* model status
* command palette
* keyboard shortcuts
* session persistence

The goal is a coding workspace, not simply a prettier REPL.

---

# Host & Hardware Constraints

PI-AI-CODER targets multiple Linux hosts, not just one machine:

* Raspberry Pi 5 (16 GB RAM) -- constrained CPU, no GPU, llama.cpp + GGUF
* Ubuntu/Debian workstations (e.g. an ASRock desktop) -- more RAM/CPU,
  possibly a GPU, often running Ollama as a service
* other Linux systems in the future

Do not hard-code hardware assumptions (thread counts, GPU layers, context
sizes, paths, setup commands) as universal defaults anywhere in
`pi_ai_coder/`. Those values belong in configuration -- defaults in
`pi_ai_coder/config.py`, per-host overrides via `config.yaml` and its
optional `profiles:` section (see `config.example.yaml`).

Build one application with configurable backends, not separate Pi/workstation
versions.

Keep resource usage under control regardless of host.

Avoid:

* Electron
* heavyweight ML frameworks unless absolutely necessary
* loading entire repositories into RAM
* unnecessary daemons
* unnecessary databases
* constant recursive filesystem scans
* excessive polling
* unnecessary web servers
* dependencies that provide little value

Prefer:

* Python standard library
* Textual
* Rich
* subprocess
* small focused dependencies

Every dependency should justify its existence.

---

# Model Backend

PI-AI-CODER supports multiple local model backends behind one
`ModelProvider` interface (`pi_ai_coder/models/base.py`):

* `LlamaCppProvider` (`pi_ai_coder/models/llama_cpp_provider.py`) -- llama.cpp,
  GGUF models. Useful for Pi deployments, systems without Ollama, or direct
  low-level model configuration. Do not remove this when working on Ollama
  support.
* `OllamaProvider` (`pi_ai_coder/models/ollama_provider.py`) -- talks to an
  already-running Ollama server over its HTTP API
  (`http://127.0.0.1:11434` by default). Never shells out to the `ollama`
  binary and never starts a server process -- assume Ollama is already
  running as a service.
* `FakeModelProvider` -- deterministic backend for tests/dev (`--fake-model`).

`pi_ai_coder/models/factory.py` (`create_provider(config, fake_model=...)`)
is the *only* place that branches on which provider is active, selected via
`config.model.provider` ("llama_cpp" or "ollama"), a `--provider` CLI flag,
or a named host profile. The CLI and TUI must only ever call through the
`ModelProvider` interface -- never branch on provider-specific details or
construct a concrete provider class directly.

Do not tightly couple the application to:

* Qwen2.5
* one GGUF model
* one prompt format
* one llama.cpp executable name (it looks for `llama-cli` or `main`)
* one provider

Future providers (OpenAI-compatible local servers, remote APIs, custom Realm
model services) should be addable by implementing `ModelProvider` and
registering them in the factory -- nothing else should need to change.

---

# Streaming

Streaming is important.

The UI should receive model output incrementally.

Do not make the user wait for an entire generation before displaying anything.

Model execution must not freeze the UI.

Use appropriate:

* workers
* threads
* async bridges
* subprocess streaming

Cancellation must terminate inference cleanly.

Handle:

* stdout
* stderr
* process exit
* cancellation
* timeouts
* exceptions

correctly.

---

# Application Core

Move application behavior out of `assistant.py` where appropriate.

The CLI should become a consumer of reusable services rather than owning application logic.

A service-oriented structure is preferred.

For example:

```text
pi_ai_coder/
    core/
    context/
    models/
    tools/
    tui/
```

This is guidance, not a rigid requirement.

Do not create unnecessary abstractions just to satisfy a directory layout.

---

# Tool System

Implemented: `ShellTool`, `GitTool`, `FileTool` (`pi_ai_coder/tools/`) and
`SearchTool` (`pi_ai_coder/tools/search.py`, ripgrep with a Python
fallback). `FileTool` covers read/write/create/apply_patch/delete/move/
list_directory/find_files/read_file_range, all path-safety checked.

`pi_ai_coder/agent/tools.py`'s `ToolRegistry` wraps these same instances
for the agent loop -- it adds argument validation, output capping, and
risk classification, but contains no file/shell/git logic of its own. The
CLI and TUI construct one `FileTool`/`GitTool`/`ShellTool`/`SearchTool` set
per project and hand it to both `AssistantService` (chat/context) and
`ToolRegistry`/`AgentService` (the agent loop) -- never duplicated.

Do not duplicate shell, Git, or file logic in the agent layer, the CLI, or
the TUI -- add capability to the tool classes in `pi_ai_coder/tools/` and
expose it through `ToolRegistry` if the agent needs it too.

---

# Agent Architecture

PI-AI-CODER has a real agent/tool loop: `pi_ai_coder/agent/`. This is now
the default behavior for a plain query in both the CLI and the TUI (opt out
with `--no-agent` on the CLI for one-shot chat with no tool use).

```text
User task
    |
    v
AgentService.run_task() (pi_ai_coder/agent/service.py)
    |
    v
model.stream_chat() -- text-based <tool_call>{...}</tool_call> protocol,
    |                  parsed by pi_ai_coder/agent/parsing.py; provider-
    |                  independent (works identically for llama.cpp, Ollama,
    |                  and the fake test provider -- see protocol.py's
    |                  ToolCall/ToolResult/AgentEvent types)
    v
ToolRegistry.classify() -- risk check (pi_ai_coder/agent/permissions.py)
    |
    v
DESTRUCTIVE? -> approval callback (blocks; CLI prompts, TUI shows a modal)
    |
    v
ToolRegistry.execute() -- dispatches to the existing FileTool/GitTool/
    |                      ShellTool/SearchTool (no logic duplicated here)
    v
Result fed back to the model; loop continues until it responds with plain
prose (no tool_call block), or a bounded limit is hit (max_iterations,
max_tool_calls) -- never unbounded autonomy.
```

The loop only ever emits `AgentEvent`s (`pi_ai_coder/agent/events.py`) --
it never prints or renders anything itself; the CLI and TUI each render
those events (compact "● Read src/auth.py" action lines, streamed prose,
a final summary).

Native provider tool-calling (Ollama's `tools` API, etc.) is not used --
the text-based fallback protocol is used uniformly for every provider so
the agent never depends on one provider's capabilities. This remains a
clean extension point if a provider-specific fast path is ever added later
(it would produce the same internal `ToolCall` objects).

---

# Tool Permissions

The risk model described in the original design is implemented as-is:

```text
READ
WRITE
EXECUTE
DESTRUCTIVE
```

`pi_ai_coder/agent/permissions.py` implements the policy below; only
DESTRUCTIVE ever blocks on an approval callback.

## READ

Examples: read_file, read_file_range, list_directory, find_files,
search_code, git_status, git_diff.

Allowed automatically inside the active project.

## WRITE

Examples: write_file, create_file, apply_patch, delete_file (single files
only -- see below), move_file.

Allowed automatically during an active coding task, inside the project
boundary -- these are expected, ordinary coding-agent actions. The TUI
visibly reports every file it touches (a "● Patch path" action line, a
FILE_CHANGED event that refreshes the git panel/project tree). Do not add
a confirmation prompt for ordinary edits -- that would defeat the point.

## EXECUTE

Examples: run_command/run_tests running things like pytest, ruff, mypy,
npm test, cargo test, git status/diff -- see `TOOL_RISK`/`classify_command`
for the full policy, not a hard-coded allowlist.

Allowed automatically during an active coding task, with the project as
cwd (or an explicit project-relative `cwd` argument). Output is captured
and capped; a command that looks destructive is escalated below.

## DESTRUCTIVE

Examples: `rm -rf`, `git reset --hard`, `git clean -f*`, `git push`
(with or without `--force`), `git commit`, `git rebase`, `git merge`,
`git checkout --`/`git restore`, `sudo`, `shutdown`/`reboot`, piping a
remote script into a shell, and bulk/directory deletion (the agent's
`delete_file` tool refuses directories entirely for this reason -- a
directory delete must go through an approved shell command).

Never executed automatically. `AgentService` calls the injected `approve`
callback and blocks until the user responds -- the CLI prompts inline, the
TUI shows `ApprovalScreen`. A denial is fed back to the model as a failed
tool result instructing it not to retry that exact command.

---

# Project Boundary

By default, operations should remain inside the currently opened project.

Do not modify files outside the project unless explicitly requested.

Use resolved filesystem paths when validating boundaries.

Be careful with:

* `..`
* symlinks
* absolute paths
* shell expansion

Do not assume a path is safe simply because its string begins with the project directory.

---

# Git Safety

Git operations must be conservative.

Safe read operations include:

```bash
git status
git diff
git log
git branch
git rev-parse
```

Never automatically perform:

```bash
git reset --hard
git clean -fd
git checkout -- .
git restore .
git push --force
git rebase
git merge
git commit
```

unless explicitly requested by the user.

Never silently discard user work.

Before changing files, understand the current Git state when relevant.

---

# File Editing

Preserve user work.

When modifying existing files:

1. Read the relevant file.
2. Understand surrounding code.
3. Make the smallest reasonable change.
4. Avoid unrelated formatting churn.
5. Avoid rewriting an entire file for a tiny modification.
6. Preserve comments and documentation unless obsolete.
7. Run relevant tests afterward.

Prefer patch-style changes.

---

# Existing CLI Compatibility

Do not casually break existing usage.

Current workflows include commands and behavior such as:

```text
add
remove
files
clear
auto
exec
save
diff
reset
help
quit
```

and one-shot querying.

Refactoring may change internal implementation, but existing user behavior should remain functional whenever practical.

If compatibility must be broken, document exactly why.

**Documented exception:** plain queries (no leading command) now run the
full agent loop by default instead of returning a single plain-chat
response -- this is the intended behavior of the agent milestone, not an
accident. `--no-agent` restores the old plain one-shot-chat behavior
exactly. All of `add`/`remove`/`files`/`clear`/`auto`/`exec`/`save`/`diff`/
`reset`/`help`/`quit` are unchanged and unaffected either way.

---

# Context System

The existing context system is valuable.

Preserve:

* ignored-file handling
* semantic-ish chunking
* relevance scoring
* context size limits
* file cache

Improve it incrementally.

Do not replace it with "read every file and send everything to the model."

Future improvements may include:

* embeddings
* symbol indexing
* repository maps
* AST parsing
* ripgrep integration
* Qdrant integration

Do not implement these unless requested or necessary.

---

# Ignore Rules

Large/generated/private directories should not enter AI context or file indexing unnecessarily.

Common ignores include:

```text
.git/
__pycache__/
*.pyc
venv/
.venv/
node_modules/
build/
dist/
.cache/
models/
*.gguf
```

Respect existing ignore behavior.

If adding a new ignore mechanism, make it compatible with existing logic where practical.

---

# Session Data

Conversation/session state must not accidentally enter Git.

Store runtime state in something similar to:

```text
.pi-ai-coder/
```

or an appropriate user-state directory.

Ensure project-local runtime state is ignored by Git.

Session persistence may contain:

* recent conversation
* selected context files
* UI layout state
* recent prompts

Do not store secrets unnecessarily.

---

# Configuration

Configuration should eventually support values like:

```yaml
model:
  path:
  context_size:
  temperature:
  threads:
  max_tokens:

ui:
  theme:
  show_token_usage:

project:
  auto_context:
  max_file_size_kb:
```

Provide sensible defaults.

The program must remain usable without requiring the user to manually create a config file.

Configuration precedence should eventually be clear and documented.

A reasonable order is:

```text
built-in defaults
    <
config file
    <
environment variables
    <
CLI arguments
```

Do not add complexity unless needed.

---

# Testing

New backend functionality should be testable without loading a real multi-gigabyte model.

Prefer dependency injection and fake providers.

Maintain a fake model backend capable of deterministic streaming.

Example:

```text
pi-coder --fake-model
```

or equivalent.

Tests should cover important logic such as:

* context management
* path validation
* config loading
* session persistence
* shell execution results
* Git parsing
* model events
* cancellation

Do not require actual llama.cpp inference for ordinary unit tests.

Integration tests may test llama.cpp separately.

---

# Error Handling

Errors should be visible and understandable.

Do not swallow exceptions silently.

Backend services should return or raise structured errors that the UI can display.

Differentiate:

* model failure
* tool failure
* filesystem error
* Git error
* invalid config
* cancelled operation
* timeout

Do not dump huge Python tracebacks into the normal user interface unless debug mode is enabled.

---

# Logging

Use proper logging rather than scattered debug `print()` statements for internal diagnostics.

Normal user-facing output belongs in the UI.

Debug logs may contain:

* model launch command metadata
* timing
* context size
* tool execution state
* exceptions

Do not log secrets.

---

# Security

Never assume model-generated shell commands are safe.

Treat model output as untrusted input.

Do not execute code just because it appeared in an AI response.

Do not interpolate untrusted strings into shell commands unnecessarily.

Prefer argument arrays over `shell=True` when possible.

If shell syntax is genuinely required, make that explicit.

---

# Code Quality

Use:

* clear names
* type hints where useful
* dataclasses where appropriate
* small focused classes/functions
* docstrings for important public interfaces
* comments for non-obvious reasoning

Avoid:

* massive god classes
* 1,000+ line UI files
* unnecessary inheritance
* speculative abstraction
* duplicate implementations
* magic global state

Favor readability.

---

# TUI Guidelines

The Textual application should be modular.

Prefer separate widgets/components for major areas such as:

```text
ProjectTree
ConversationView
PromptInput
ContextPanel
ToolOutput
GitPanel
StatusBar
```

Names may differ.

Do not place the entire application in one file.

The interface should remain usable at normal terminal sizes.

Support keyboard-first interaction.

Mouse support is welcome but must not be required.

---

# TUI Responsiveness

Never run long operations directly on the Textual event loop.

This includes:

* model inference
* recursive scans
* long Git commands
* shell commands
* test suites

Use workers or appropriate async/thread mechanisms.

Always restore the UI to a valid state after:

* cancellation
* subprocess failure
* model crash
* malformed output

---

# Command Palette

Where practical, expose important actions through a command palette.

Typical actions:

* Open file
* Add file to context
* Remove file from context
* Clear context
* Toggle auto context
* Run command
* Show Git status
* Show Git diff
* Reset conversation
* Change model
* Reload project
* Show keyboard shortcuts
* Quit

Keyboard bindings should also exist for frequent actions.

---

# Documentation

When architecture or user behavior changes, update documentation.

Relevant files include:

* `README.md`
* `QUICKSTART.md`
* `DOCUMENTATION.md`
* `PROJECT_STRUCTURE.md`

Do not allow documentation to drift significantly behind the implementation.

Do not delete useful Raspberry Pi setup documentation while adding TUI documentation.

---

# Dependency Management

Before adding a dependency, ask:

1. Is this already possible with stdlib?
2. Does the dependency provide meaningful value?
3. Is it maintained?
4. Is it reasonable on Raspberry Pi?
5. Does it significantly increase setup complexity?

Textual and Rich are acceptable for the TUI.

Keep the rest lean.

---

# Development Workflow

For substantial changes:

1. Inspect current repository state.
2. Read relevant files.
3. Check Git status.
4. Explain the intended change briefly.
5. Make focused edits.
6. Run relevant tests.
7. Run syntax/static checks where available.
8. Review `git diff`.
9. Fix regressions.
10. Update documentation when necessary.

Do not declare work complete without reviewing the resulting diff.

---

# Commands To Prefer During Development

Useful read-only checks:

```bash
git status --short
git diff
git diff --stat
git branch --show-current
python -m compileall .
```

When tests exist:

```bash
pytest
```

or:

```bash
python -m pytest
```

Do not install random global Python packages.

Use the project's virtual environment.

---

# Virtual Environment

Prefer:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

or preserve the existing project's environment convention if one already exists.

Do not unnecessarily use `sudo pip`.

---

# Definition of Good Changes

A good PI-AI-CODER change:

* preserves existing useful behavior
* makes the architecture easier to extend
* remains lightweight
* works well on the Pi
* is understandable
* is testable
* does not destroy user work
* improves the real coding workflow
* moves the project closer to a true coding agent/workspace

A bad change:

* rewrites working code for style alone
* adds large dependencies unnecessarily
* hides logic inside UI code
* executes model-generated commands automatically
* breaks CLI behavior without reason
* creates fake buttons/features
* loads entire repositories blindly
* ignores resource limits
* introduces unsafe filesystem or Git behavior

---

# Current Priority

The workspace foundation (items 1-10 below) is done. The current major
development priority is polishing the agent loop itself -- not building
another foundational layer.

Completed foundation:

1. Separate the backend from the current CLI.
2. Preserve existing CLI behavior.
3. Introduce clean tool/service interfaces.
4. Add a fake model backend.
5. Build a Textual TUI.
6. Add streaming responses.
7. Integrate project files and context management.
8. Integrate shell/tool output.
9. Integrate Git status and diff.
10. Add session persistence and polish.
11. Portable project roots, multi-provider support (llama.cpp + Ollama), host profiles.
12. A real bounded agent/tool loop (`pi_ai_coder/agent/`): inspect, search, read,
    edit (write/create/patch/delete/move), run commands/tests, iterate, summarize --
    this is the default behavior for a plain query now, not a separate opt-in mode.

Still open, in roughly this order:

* A checkpoint/undo layer beyond bare git (explicitly deferred, not a blocker).
* In-place file editing in the preview pane (currently read-only).
* A native provider tool-calling fast path, if it ever earns its complexity
  over the text-based fallback protocol that already works uniformly.

Do not regress the agent loop back to unrestricted/unbounded autonomy, and
do not remove the approval gate on DESTRUCTIVE actions while "polishing."

---

# Final Rule

PI-AI-CODER should remain something we understand and control.

Prefer transparent local components over opaque complexity.

Build it into a serious tool one layer at a time.
