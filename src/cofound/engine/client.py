"""The engine: Cofound's single chokepoint for all model calls.

Nothing else in the codebase imports `claude_agent_sdk`. If we ever change SDK,
model, or auth strategy, it happens here.

Auth model (CLAUDE.md non-negotiables):
  - Subscription auth only. The Agent SDK spawns the Claude Code CLI as a
    subprocess; with no ANTHROPIC_API_KEY set, that subprocess uses the OAuth
    credential created by `claude` / `claude login`. We therefore pass nothing
    that sets an API key and never use --bare.
  - We do not require or read ANTHROPIC_API_KEY. (If a user happens to have one
    exported, the underlying CLI may use it — we surface that in the preflight
    so the credit story stays honest, but we never set it ourselves.)

Streaming contract:
  `ask(...)` is an async generator of `EngineEvent`s. Callers iterate it and
  react to text deltas, tool activity, and a terminal `DoneEvent` carrying the
  session id + usage. On failure it raises a typed `CofoundEngineError`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Sequence

from .errors import AuthMissing, CofoundEngineError, classify_sdk_error

# ---------------------------------------------------------------------------
# Streaming events — plain dataclasses (hot path; no validation needed).
# ---------------------------------------------------------------------------


@dataclass
class TextEvent:
    """A chunk of assistant-visible text."""

    text: str


@dataclass
class ToolEvent:
    """The cofounder used a tool (e.g. wrote to the canvas)."""

    name: str
    # A short, human-facing summary for the status line, when we can derive one.
    summary: str | None = None


@dataclass
class StatusEvent:
    """A non-text lifecycle signal ('thinking', 'planning', ...)."""

    message: str


@dataclass
class DoneEvent:
    """Terminal event for a turn: the session id to resume + usage info."""

    session_id: str | None
    is_error: bool = False
    num_turns: int | None = None
    total_cost_usd: float | None = None
    usage: dict | None = None
    duration_ms: int | None = None


EngineEvent = TextEvent | ToolEvent | StatusEvent | DoneEvent


# ---------------------------------------------------------------------------
# Preflight (no model call) — advisory environment check.
# ---------------------------------------------------------------------------


@dataclass
class EnvStatus:
    """Best-effort, no-cost view of whether we can talk to the subscription."""

    sdk_importable: bool
    has_api_key: bool
    has_oauth_creds: bool
    likely_ready: bool
    detail: str = ""
    extras: dict = field(default_factory=dict)


def _macos_keychain_credential_present() -> bool:
    """On macOS, check the login keychain for the Claude Code credential.

    We call `security find-generic-password -s <service>` WITHOUT `-w`, so we
    only probe for the item's existence and never request the secret itself —
    this does not trigger a keychain access prompt.
    """
    if sys.platform != "darwin":
        return False
    import shutil
    import subprocess

    security = shutil.which("security")
    if not security:
        return False
    for service in ("Claude Code-credentials", "Claude Code"):
        try:
            result = subprocess.run(
                [security, "find-generic-password", "-s", service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            continue
        if result.returncode == 0:
            return True
    return False


def _oauth_credentials_present() -> bool:
    """Heuristically detect a `claude login` credential without prompting.

    The CLI stores its OAuth credential under the macOS login keychain and/or as
    a file under the home directory. We only do cheap, non-interactive checks
    here — the authoritative test is making one real call. False here means "we
    found no evidence of a login", not a hard "definitely logged out".
    """
    home = Path.home()
    claude_dir = home / ".claude"
    file_candidates = [
        claude_dir / ".credentials.json",
        claude_dir / "credentials.json",
        home / ".claude.json",  # written by Claude Code on this platform
    ]
    if any(p.exists() for p in file_candidates):
        return True
    if _macos_keychain_credential_present():
        return True
    return False


def preflight() -> EnvStatus:
    """Check, without spending credit, whether the engine is likely usable."""
    try:
        import claude_agent_sdk  # noqa: F401

        sdk_importable = True
    except Exception:
        sdk_importable = False

    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_oauth = _oauth_credentials_present()

    likely_ready = sdk_importable and (has_oauth or has_api_key)

    if not sdk_importable:
        detail = "The claude-agent-sdk package isn't importable. Run `uv sync`."
    elif not (has_oauth or has_api_key):
        detail = (
            "No Claude login detected. Run `claude` and log in to your plan."
        )
    elif has_api_key:
        detail = (
            "Note: ANTHROPIC_API_KEY is set in your environment. Cofound is "
            "designed for subscription auth; the underlying CLI may use the API "
            "key (billed separately) instead of your subscription."
        )
    else:
        detail = "Subscription login detected."

    return EnvStatus(
        sdk_importable=sdk_importable,
        has_api_key=has_api_key,
        has_oauth_creds=has_oauth,
        likely_ready=likely_ready,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class Engine:
    """Wraps the Claude Agent SDK with subscription auth and session continuity.

    A single Engine instance can carry the "current" session id so multi-turn
    chat resumes automatically. Isolated calls (e.g. Ultraplan) should pass
    `resume=None` and ignore the stored session.
    """

    def __init__(self, *, default_cwd: str | Path | None = None) -> None:
        self.default_cwd = Path(default_cwd) if default_cwd else None
        # The most recent chat session id, so the next turn can resume it.
        self.last_session_id: str | None = None

    # -- public API ---------------------------------------------------------

    async def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: Sequence[str] | None = None,
        resume: str | None = None,
        cwd: str | Path | None = None,
        permission_mode: str = "bypassPermissions",
        track_session: bool = True,
    ) -> AsyncIterator[EngineEvent]:
        """Stream a single turn from the model.

        Yields `EngineEvent`s; finishes with a `DoneEvent`. Raises a typed
        `CofoundEngineError` on auth/credit/other failure.

        Args:
            prompt: the user/system turn text.
            system: optional system prompt (the persona).
            tools: allowed built-in tool names (e.g. ["Read", "Write", "Edit"]).
            resume: a session id to continue; if omitted, uses this engine's
                last session id when `track_session` is True.
            cwd: working directory for tool/file operations (the workspace).
            permission_mode: SDK permission mode. We default to
                "bypassPermissions" because Cofound is the user's own local
                agent operating on its own workspace; gating each canvas write
                behind a prompt would break the flow.
            track_session: when True, store the resulting session id on the
                engine and default `resume` to it.
        """
        # Resolve session continuity.
        resume_id = resume
        if resume_id is None and track_session:
            resume_id = self.last_session_id

        work_dir = Path(cwd) if cwd else self.default_cwd

        # Import lazily so the rest of the app (and tests) don't hard-depend on
        # the SDK being installed.
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ResultMessage,
                SystemMessage,
                TextBlock,
                ToolUseBlock,
                query,
            )
        except ImportError as exc:  # pragma: no cover - exercised only w/o SDK
            raise CofoundEngineError(
                "The claude-agent-sdk package isn't installed. Run `uv sync`.",
                detail=str(exc),
            ) from exc

        options = ClaudeAgentOptions(
            system_prompt=system,
            allowed_tools=list(tools) if tools else [],
            permission_mode=permission_mode,
            resume=resume_id,
            cwd=str(work_dir) if work_dir else None,
        )

        captured_session: str | None = resume_id

        try:
            async for message in query(prompt=prompt, options=options):
                # Capture the session id as early as possible.
                if isinstance(message, SystemMessage):
                    if message.subtype == "init":
                        sid = message.data.get("session_id")
                        if sid:
                            captured_session = sid
                    continue

                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                yield TextEvent(text=block.text)
                        elif isinstance(block, ToolUseBlock):
                            yield ToolEvent(
                                name=block.name,
                                summary=_tool_summary(block),
                            )
                    continue

                if isinstance(message, ResultMessage):
                    if message.session_id:
                        captured_session = message.session_id
                    if track_session and captured_session:
                        self.last_session_id = captured_session
                    yield DoneEvent(
                        session_id=captured_session,
                        is_error=message.is_error,
                        num_turns=message.num_turns,
                        total_cost_usd=message.total_cost_usd,
                        usage=message.usage,
                        duration_ms=message.duration_ms,
                    )
                    return

        except CofoundEngineError:
            raise
        except Exception as exc:  # translate everything else to a typed error
            raise classify_sdk_error(exc) from exc

        # Stream ended without a ResultMessage — emit a best-effort Done so
        # callers always see a terminal event.
        if track_session and captured_session:
            self.last_session_id = captured_session
        yield DoneEvent(session_id=captured_session, is_error=False)

    async def collect_text(self, prompt: str, **kwargs) -> str:
        """Convenience: run `ask` and return the concatenated text.

        Useful for isolated, non-interactive calls (e.g. the throwaway smoke
        test and, later, Ultraplan when it doesn't need streaming).
        """
        chunks: list[str] = []
        async for event in self.ask(prompt, **kwargs):
            if isinstance(event, TextEvent):
                chunks.append(event.text)
        return "".join(chunks)


def _tool_summary(block) -> str | None:
    """Derive a short human label for a tool use, for the status line."""
    name = getattr(block, "name", "")
    tool_input = getattr(block, "input", None) or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    if name in {"Write", "Edit"} and path:
        return f"writing {Path(str(path)).name}"
    if name == "Read" and path:
        return f"reading {Path(str(path)).name}"
    if name:
        return name
    return None


__all__ = [
    "Engine",
    "EngineEvent",
    "TextEvent",
    "ToolEvent",
    "StatusEvent",
    "DoneEvent",
    "EnvStatus",
    "preflight",
]
