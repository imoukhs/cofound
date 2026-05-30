"""Machine state for a workspace: `.cofound/config.json` and `.cofound/state.json`.

JSON is for machine state only (per CLAUDE.md); human-facing content is Markdown
elsewhere on the canvas. Models are pydantic v2 so they validate and serialize
cleanly.

This module also hosts the low-level atomic text writer used across the canvas,
because it has no dependencies on the other canvas modules (so importing it never
creates a cycle).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

# Schema version for the on-disk machine state. Bump if the shape changes.
STATE_SCHEMA_VERSION = 1

# Canonical sub-paths inside a workspace.
COFOUND_DIR = ".cofound"
CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
LOG_DIR = "log"
PLAN_FILE = "PLAN.md"
DOCS_DIR = "docs"
NOTES_DIR = "notes"


def utcnow_iso() -> str:
    """An ISO-8601 UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    """Write text to `path` atomically (write temp + os.replace).

    Prevents half-written files if the process dies mid-write — important since
    the UI watches these files and re-renders on change.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WorkspaceConfig(BaseModel):
    """Stable workspace settings — written once at creation, rarely changed."""

    name: str
    created_at: str = Field(default_factory=utcnow_iso)
    schema_version: int = STATE_SCHEMA_VERSION


class WorkspaceState(BaseModel):
    """Mutable per-session state."""

    # The current chat session id, so the cofounder resumes across app restarts.
    session_id: str | None = None
    # Where the project is in its lifecycle. Drives first-run vs normal flow.
    phase: str = "onboarding"
    # When Ultraplan last ran (ISO). None until the first plan is written.
    last_plan_at: str | None = None
    # Whether the first-run context-gathering flow has completed.
    onboarded: bool = False
    updated_at: str = Field(default_factory=utcnow_iso)

    def touch(self) -> None:
        """Update the modified timestamp."""
        self.updated_at = utcnow_iso()


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------


def _cofound_dir(root: Path) -> Path:
    return root / COFOUND_DIR


def config_path(root: Path) -> Path:
    return _cofound_dir(root) / CONFIG_FILE


def state_path(root: Path) -> Path:
    return _cofound_dir(root) / STATE_FILE


def load_config(root: Path) -> WorkspaceConfig:
    raw = json.loads(config_path(root).read_text(encoding="utf-8"))
    return WorkspaceConfig.model_validate(raw)


def save_config(root: Path, config: WorkspaceConfig) -> None:
    atomic_write_text(
        config_path(root), json.dumps(config.model_dump(), indent=2) + "\n"
    )


def load_state(root: Path) -> WorkspaceState:
    raw = json.loads(state_path(root).read_text(encoding="utf-8"))
    return WorkspaceState.model_validate(raw)


def save_state(root: Path, state: WorkspaceState) -> None:
    state.touch()
    atomic_write_text(
        state_path(root), json.dumps(state.model_dump(), indent=2) + "\n"
    )
