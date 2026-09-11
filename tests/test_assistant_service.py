from pi_ai_coder.context.manager import ContextManager
from pi_ai_coder.core.assistant_service import AssistantService
from pi_ai_coder.core.events import EventType
from pi_ai_coder.core.session import SessionState
from pi_ai_coder.models.fake_provider import FakeModelProvider


def make_service(tmp_path, response="hello world", auto_context=False):
    provider = FakeModelProvider(response=response)
    context_manager = ContextManager()
    session = SessionState(auto_context=auto_context)
    return AssistantService(
        provider=provider,
        context_manager=context_manager,
        session=session,
        project_root=str(tmp_path),
    ), provider


def test_chat_records_conversation_and_code_blocks(tmp_path):
    service, _ = make_service(tmp_path, response="```python\nprint(1)\n```")
    response = service.chat("write hello world")

    assert response == "```python\nprint(1)\n```"
    assert service.session.conversation[-2] == {"role": "user", "content": "write hello world"}
    assert service.session.conversation[-1]["role"] == "assistant"
    assert service.last_code_blocks[0]["code"] == "print(1)"


def test_stream_chat_emits_status_then_tokens_then_done(tmp_path):
    service, _ = make_service(tmp_path, response="hi there")
    events = list(service.stream_chat("say hi"))

    types = [e.type for e in events]
    assert EventType.STATUS in types
    assert EventType.TOKEN in types
    assert types[-1] == EventType.DONE

    assert service.session.conversation[-1]["content"] == "hi there"


def test_add_remove_clear_context_files(tmp_path):
    service, _ = make_service(tmp_path)
    service.add_context_files(["a.py", "b.py"])
    assert service.session.context_files == ["a.py", "b.py"]

    service.add_context_files(["a.py"])  # no duplicate
    assert service.session.context_files == ["a.py", "b.py"]

    service.remove_context_files("a.py")
    assert service.session.context_files == ["b.py"]

    service.clear_context_files()
    assert service.session.context_files == []


def test_toggle_auto_context(tmp_path):
    service, _ = make_service(tmp_path, auto_context=True)
    assert service.toggle_auto_context() is False
    assert service.toggle_auto_context() is True


def test_reset_clears_conversation_but_not_context_files(tmp_path):
    service, _ = make_service(tmp_path)
    service.add_context_files(["a.py"])
    service.chat("hello")
    assert service.session.conversation

    service.reset()
    assert service.session.conversation == []
    assert service.session.context_files == ["a.py"]


def test_discover_project_files_respects_ignore_and_extensions(tmp_path):
    service, _ = make_service(tmp_path)
    (tmp_path / "main.py").write_text("print(1)\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_text("junk")

    discovered = service.discover_project_files("fix the python bug")
    assert any(f.endswith("main.py") for f in discovered)
    assert not any("cache.pyc" in f for f in discovered)
