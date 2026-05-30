"""Shared test fixtures.

Hard rule (CLAUDE.md): tests never call the real model. The `mock_engine`
fixture is a drop-in for `cofound.engine.Engine` that yields scripted events and
records the prompts it was given — so prompt-assembly and canvas logic can be
tested without spending a cent of credit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator

import pytest

from cofound.canvas import Workspace
from cofound.engine import DoneEvent, EngineEvent, TextEvent, ToolEvent


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    """A freshly created, isolated workspace in a temp directory."""
    return Workspace.create(tmp_path / "proj", name="Test Project")


@dataclass
class MockEngine:
    """A fake Engine that never touches the SDK.

    Configure `scripted_text` for what `ask` should "say", and inspect
    `calls` to assert on the prompts/options it received.
    """

    scripted_text: str = "ok"
    tool_events: list[ToolEvent] = field(default_factory=list)
    last_session_id: str | None = None
    calls: list[dict] = field(default_factory=list)
    _session_counter: int = 0

    async def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools=None,
        resume: str | None = None,
        cwd=None,
        permission_mode: str = "bypassPermissions",
        track_session: bool = True,
    ) -> AsyncIterator[EngineEvent]:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "tools": list(tools) if tools else [],
                "resume": resume if resume is not None else self.last_session_id,
                "cwd": str(cwd) if cwd else None,
            }
        )
        for ev in self.tool_events:
            yield ev
        if self.scripted_text:
            yield TextEvent(text=self.scripted_text)

        self._session_counter += 1
        session_id = resume or self.last_session_id or f"mock-session-{self._session_counter}"
        if track_session:
            self.last_session_id = session_id
        yield DoneEvent(
            session_id=session_id,
            is_error=False,
            num_turns=1,
            total_cost_usd=0.0,
            usage={"input_tokens": 1, "output_tokens": 1},
        )

    async def collect_text(self, prompt: str, **kwargs) -> str:
        chunks: list[str] = []
        async for ev in self.ask(prompt, **kwargs):
            if isinstance(ev, TextEvent):
                chunks.append(ev.text)
        return "".join(chunks)


@pytest.fixture
def mock_engine() -> MockEngine:
    return MockEngine()
