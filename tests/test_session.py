from pi_ai_coder.core.session import SessionState, SessionStore


def test_add_turn_caps_history():
    state = SessionState()
    for i in range(100):
        state.add_turn("user", f"msg-{i}")
    assert len(state.conversation) <= 40


def test_add_prompt_caps_recent_prompts():
    state = SessionState()
    for i in range(100):
        state.add_prompt(f"prompt-{i}")
    assert len(state.recent_prompts) <= 50
    assert state.recent_prompts[-1] == "prompt-99"


def test_roundtrip_save_and_load(tmp_path):
    store = SessionStore(project_root=str(tmp_path))
    state = SessionState(context_files=["a.py"], auto_context=False)
    state.add_turn("user", "hello")
    state.add_turn("assistant", "hi there")

    store.save(state)
    loaded = store.load()

    assert loaded.context_files == ["a.py"]
    assert loaded.auto_context is False
    assert loaded.conversation == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_load_missing_file_returns_defaults(tmp_path):
    store = SessionStore(project_root=str(tmp_path))
    state = store.load()
    assert state.context_files == []
    assert state.auto_context is True


def test_load_corrupt_file_returns_defaults(tmp_path):
    store = SessionStore(project_root=str(tmp_path))
    store.state_dir.mkdir(parents=True)
    store.state_file.write_text("{not valid json")
    state = store.load()
    assert state.context_files == []


def test_ensure_gitignored_appends_entry(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n")
    store = SessionStore(project_root=str(tmp_path))

    changed = store.ensure_gitignored()
    assert changed is True
    assert ".pi-ai-coder/" in gitignore.read_text()

    changed_again = store.ensure_gitignored()
    assert changed_again is False


def test_ensure_gitignored_noop_without_gitignore(tmp_path):
    store = SessionStore(project_root=str(tmp_path))
    assert store.ensure_gitignored() is False
