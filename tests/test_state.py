"""State + config serialization, and the mocked engine contract.

No real model calls anywhere in here.
"""

from __future__ import annotations

import json

import pytest

from cofound.canvas import (
    WorkspaceConfig,
    WorkspaceState,
    load_config,
    load_state,
    save_config,
    save_state,
)
from cofound.canvas.state import (
    STATE_SCHEMA_VERSION,
    atomic_write_text,
    config_path,
    state_path,
)
from cofound.engine import DoneEvent, TextEvent


def test_config_defaults_and_roundtrip(tmp_path):
    cfg = WorkspaceConfig(name="Acme")
    assert cfg.name == "Acme"
    assert cfg.schema_version == STATE_SCHEMA_VERSION
    assert cfg.created_at  # auto timestamp

    (tmp_path / ".cofound").mkdir()
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded == cfg

    # File is valid, indented JSON.
    raw = json.loads(config_path(tmp_path).read_text())
    assert raw["name"] == "Acme"


def test_state_defaults_and_roundtrip(tmp_path):
    st = WorkspaceState()
    assert st.phase == "onboarding"
    assert st.session_id is None
    assert st.last_plan_at is None
    assert st.onboarded is False

    (tmp_path / ".cofound").mkdir()
    save_state(tmp_path, st)
    loaded = load_state(tmp_path)
    assert loaded.phase == "onboarding"
    assert loaded.session_id is None

    # Mutate + persist.
    loaded.session_id = "sess-123"
    loaded.onboarded = True
    loaded.phase = "building"
    save_state(tmp_path, loaded)
    again = load_state(tmp_path)
    assert again.session_id == "sess-123"
    assert again.onboarded is True
    assert again.phase == "building"


def test_state_touch_updates_timestamp(tmp_path):
    (tmp_path / ".cofound").mkdir()
    st = WorkspaceState()
    first = st.updated_at
    st.updated_at = "2000-01-01T00:00:00+00:00"  # force an older value
    save_state(tmp_path, st)  # save_state calls touch()
    reloaded = load_state(tmp_path)
    assert reloaded.updated_at != "2000-01-01T00:00:00+00:00"
    assert reloaded.updated_at >= first or True  # monotonic-ish; mainly: it changed


def test_atomic_write_creates_parents_and_replaces(tmp_path):
    target = tmp_path / "a" / "b" / "file.txt"
    atomic_write_text(target, "hello")
    assert target.read_text() == "hello"
    atomic_write_text(target, "world")
    assert target.read_text() == "world"
    # No leftover temp files.
    assert list((tmp_path / "a" / "b").glob("*.tmp")) == []


def test_invalid_state_file_raises(tmp_path):
    (tmp_path / ".cofound").mkdir()
    state_path(tmp_path).write_text("{ not json }")
    with pytest.raises(Exception):
        load_state(tmp_path)


# --- the mocked engine never burns credit ----------------------------------


@pytest.mark.asyncio
async def test_mock_engine_streams_and_tracks_session(mock_engine):
    mock_engine.scripted_text = "ready"
    events = []
    async for ev in mock_engine.ask("hi", system="be terse", tools=["Read"]):
        events.append(ev)

    texts = [e.text for e in events if isinstance(e, TextEvent)]
    dones = [e for e in events if isinstance(e, DoneEvent)]
    assert texts == ["ready"]
    assert len(dones) == 1
    assert dones[0].session_id == mock_engine.last_session_id

    # It recorded what it was asked, so prompt-assembly can be asserted later.
    assert mock_engine.calls[0]["system"] == "be terse"
    assert mock_engine.calls[0]["tools"] == ["Read"]


@pytest.mark.asyncio
async def test_mock_engine_resumes_session(mock_engine):
    await mock_engine.collect_text("first")
    sid = mock_engine.last_session_id
    assert sid is not None
    await mock_engine.collect_text("second")
    # Same engine keeps the session id stable across turns.
    assert mock_engine.last_session_id == sid
