"""Cofound engine — the single chokepoint for all Claude model calls.

Import the engine and its errors from here; never import `claude_agent_sdk`
anywhere else in the codebase.
"""

from .client import (
    DoneEvent,
    Engine,
    EngineEvent,
    EnvStatus,
    StatusEvent,
    TextEvent,
    ToolEvent,
    preflight,
)
from .errors import (
    AuthMissing,
    CLINotInstalled,
    CofoundEngineError,
    CreditExhausted,
    EngineFailure,
)

__all__ = [
    "Engine",
    "EngineEvent",
    "TextEvent",
    "ToolEvent",
    "StatusEvent",
    "DoneEvent",
    "EnvStatus",
    "preflight",
    "CofoundEngineError",
    "AuthMissing",
    "CreditExhausted",
    "CLINotInstalled",
    "EngineFailure",
]
