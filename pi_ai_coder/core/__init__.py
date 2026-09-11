from .events import AssistantStatus, EventType, StreamEvent
from .session import SessionState, SessionStore

__all__ = [
    "AssistantStatus",
    "EventType",
    "StreamEvent",
    "SessionState",
    "SessionStore",
    "AssistantService",
    "DEFAULT_SYSTEM_PROMPT",
]

# AssistantService is resolved lazily (PEP 562) rather than imported eagerly
# above: assistant_service.py imports pi_ai_coder.models.base, which itself
# needs pi_ai_coder.core.events -- importing assistant_service at this
# package's init time would re-enter this package mid-initialization and
# create a circular import. Deferring it until first access breaks the cycle
# while keeping `from pi_ai_coder.core import AssistantService` working.
def __getattr__(name):
    if name in ("AssistantService", "DEFAULT_SYSTEM_PROMPT"):
        from . import assistant_service
        return getattr(assistant_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
