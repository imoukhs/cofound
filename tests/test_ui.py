"""Headless TUI tests driven by Textual's run_test() + the mock engine.

These exercise the real app (layout, input, slash commands, the streaming turn,
session persistence) without a single model call.
"""

from __future__ import annotations

import pytest

from cofound.ui import CofoundApp
from cofound.ui.chat_pane import ChatMessage, ChatPane
from cofound.ui.status_bar import StatusBar


def _bubbles(app, role: str) -> list[ChatMessage]:
    return [m for m in app.query(ChatMessage) if m.role == role]


async def _wait_until(pilot, predicate, *, tries: int = 100) -> None:
    """Pump the event loop until `predicate()` is true (or we give up).

    We avoid `workers.wait_for_complete()` because the canvas pane runs a
    periodic poll, so 'all workers idle' is not a stable condition.
    """
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause(0.02)
    assert predicate(), "condition not met in time"


@pytest.mark.asyncio
async def test_turn_streams_and_persists_session(workspace, mock_engine):
    mock_engine.scripted_text = "Who, specifically, is this for?"
    app = CofoundApp(workspace, engine=mock_engine)

    async with app.run_test() as pilot:
        inp = app.query_one("#chat-input")
        inp.focus()
        inp.value = "I want to build a budgeting app"
        await pilot.press("enter")
        await _wait_until(
            pilot,
            lambda: not app._busy and bool(_bubbles(app, "cofounder")),
        )

        # The user's message and the cofounder's streamed reply are both shown.
        assert any("budgeting app" in m.text for m in _bubbles(app, "you"))
        cof = _bubbles(app, "cofounder")
        assert cof and "Who, specifically" in cof[-1].text

        # The engine was called with the assembled cofounder persona, canvas
        # tools, and the workspace as cwd.
        call = mock_engine.calls[-1]
        assert "cofounder" in call["system"].lower()
        assert "Active preferences" in call["system"]
        assert call["tools"] == ["Read", "Write", "Edit", "Glob", "Grep"]
        assert call["cwd"] == str(workspace.root)

        # Session id was captured and persisted to state.json for resume.
        assert mock_engine.last_session_id is not None
        assert workspace.state.session_id == mock_engine.last_session_id
        assert app.query_one(StatusBar).session_id == mock_engine.last_session_id


@pytest.mark.asyncio
async def test_help_command_shows_help(workspace, mock_engine):
    app = CofoundApp(workspace, engine=mock_engine)
    async with app.run_test() as pilot:
        inp = app.query_one("#chat-input")
        inp.focus()
        inp.value = "/help"
        await pilot.press("enter")
        await pilot.pause()
        sys_msgs = _bubbles(app, "system")
        assert sys_msgs and "Commands" in sys_msgs[-1].text
        # A slash command must not be sent to the engine.
        assert mock_engine.calls == []


@pytest.mark.asyncio
async def test_unknown_command(workspace, mock_engine):
    app = CofoundApp(workspace, engine=mock_engine)
    async with app.run_test() as pilot:
        inp = app.query_one("#chat-input")
        inp.focus()
        inp.value = "/nope"
        await pilot.press("enter")
        await pilot.pause()
        sys_msgs = _bubbles(app, "system")
        assert sys_msgs and "Unknown command" in sys_msgs[-1].text


@pytest.mark.asyncio
async def test_resumes_session_from_state(workspace, mock_engine):
    # Pre-seed a session id; the app should adopt it on mount so the next turn
    # resumes the prior conversation.
    state = workspace.state
    state.session_id = "prior-session-xyz"
    workspace.save_state(state)

    app = CofoundApp(workspace, engine=mock_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.engine.last_session_id == "prior-session-xyz"
        assert app.query_one(StatusBar).session_id == "prior-session-xyz"
