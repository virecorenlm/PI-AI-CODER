from pi_ai_coder.core.events import EventType
from pi_ai_coder.models.base import Message
from pi_ai_coder.models.fake_provider import FakeModelProvider


def test_chat_returns_configured_response():
    provider = FakeModelProvider(response="hello world")
    result = provider.chat([Message("user", "hi")])
    assert result == "hello world"


def test_stream_chat_yields_tokens_then_done():
    provider = FakeModelProvider(response="hello world")
    events = list(provider.stream_chat([Message("user", "hi")]))

    assert events[-1].type == EventType.DONE
    token_text = "".join(e.text for e in events if e.type == EventType.TOKEN)
    assert token_text == "hello world"


def test_cancel_stops_stream_and_emits_cancelled():
    provider = FakeModelProvider(response="one two three four five", delay=0.05)
    events = []
    gen = provider.stream_chat([Message("user", "hi")])
    for i, event in enumerate(gen):
        events.append(event)
        if i == 1:
            provider.cancel()

    assert events[-1].type == EventType.CANCELLED
