import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from pi_ai_coder.core.events import EventType
from pi_ai_coder.models.base import Message
from pi_ai_coder.models.ollama_provider import OllamaConfig, OllamaProvider


def make_provider(**kwargs):
    config = OllamaConfig(model="qwen3.5:latest", **kwargs)
    return OllamaProvider(config)


class FakeHTTPResponse(io.BytesIO):
    """Minimal stand-in for the object urlopen() returns / yields as a context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self.getvalue().splitlines(keepends=True))


def test_info_reports_host_and_model():
    provider = make_provider(host="http://example:11434")
    info = provider.info()
    assert "example:11434" in info.name
    assert info.model_name == "qwen3.5:latest"


def test_health_check_success():
    provider = make_provider()
    with patch("urllib.request.urlopen", return_value=FakeHTTPResponse(b'{"models": []}')):
        health = provider.health_check()
    assert health.available


def test_health_check_connection_refused():
    provider = make_provider()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        health = provider.health_check()
    assert not health.available
    assert "Connection refused" in health.message or "ollama serve" in health.message


def test_list_models_parses_tags_response():
    body = json.dumps({
        "models": [
            {"name": "qwen3.5:latest", "size": 123456},
            {"name": "llama3:latest", "size": 789},
        ]
    }).encode("utf-8")
    provider = make_provider()
    with patch("urllib.request.urlopen", return_value=FakeHTTPResponse(body)):
        models = provider.list_models()
    assert [m.name for m in models] == ["qwen3.5:latest", "llama3:latest"]
    assert models[0].size == 123456


def test_list_models_returns_empty_on_error():
    provider = make_provider()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        assert provider.list_models() == []


def test_set_model_updates_config():
    provider = make_provider()
    provider.set_model("llama3:latest")
    assert provider.config.model == "llama3:latest"
    assert provider.info().model_name == "llama3:latest"


def test_chat_posts_and_parses_message():
    body = json.dumps({"message": {"content": "hello there"}}).encode("utf-8")
    provider = make_provider()
    with patch("urllib.request.urlopen", return_value=FakeHTTPResponse(body)) as mock_urlopen:
        result = provider.chat([Message("user", "hi")])
    assert result == "hello there"
    request = mock_urlopen.call_args[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "qwen3.5:latest"
    assert payload["stream"] is False
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


def test_stream_chat_yields_tokens_and_done():
    lines = [
        json.dumps({"message": {"content": "hel"}, "done": False}) + "\n",
        json.dumps({"message": {"content": "lo"}, "done": False}) + "\n",
        json.dumps({"message": {"content": ""}, "done": True}) + "\n",
    ]
    body = "".join(lines).encode("utf-8")
    provider = make_provider()
    with patch("urllib.request.urlopen", return_value=FakeHTTPResponse(body)):
        events = list(provider.stream_chat([Message("user", "hi")]))

    tokens = "".join(e.text for e in events if e.type == EventType.TOKEN)
    assert tokens == "hello"
    assert events[-1].type == EventType.DONE


def test_stream_chat_reports_unreachable_server():
    provider = make_provider()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        events = list(provider.stream_chat([Message("user", "hi")]))
    assert events[0].type == EventType.ERROR
    assert "ollama serve" in events[0].text


def test_cancel_sets_flag_and_closes_response():
    provider = make_provider()
    fake_response = MagicMock()
    provider._response = fake_response
    provider.cancel()
    fake_response.close.assert_called_once()
    assert provider._cancelled.is_set()
