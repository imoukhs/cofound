"""The Workspace — a project directory that is the shared canvas.

The filesystem *is* the shared state every agent reads from and writes to. One
workspace = one product/project.

Layout (CLAUDE.md):

    <root>/
      PLAN.md
      docs/
      notes/
      .cofound/
        config.json
        state.json
        log/
"""

from __future__ import annotations

from pathlib import Path

from .documents import Documents
from .notes import Notes
from .plan import Plan
from .state import (
    COFOUND_DIR,
    DOCS_DIR,
    LOG_DIR,
    NOTES_DIR,
    PLAN_FILE,
    WorkspaceConfig,
    WorkspaceState,
    config_path,
    load_config,
    load_state,
    save_config,
    save_state,
    state_path,
)


class Workspace:
    """Typed read/write access to one canvas directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.docs = Documents(self.root / DOCS_DIR)
        self.notes = Notes(self.root / NOTES_DIR)
        self.plan = Plan(self.root / PLAN_FILE)

    # -- detection / lifecycle ---------------------------------------------

    @staticmethod
    def is_workspace(root: str | Path) -> bool:
        """True if `root` looks like an initialized Cofound workspace."""
        root = Path(root).expanduser()
        return (root / COFOUND_DIR).is_dir() and config_path(root).exists()

    @classmethod
    def create(cls, root: str | Path, name: str, *, exist_ok: bool = False) -> "Workspace":
        """Scaffold a fresh workspace and return it.

        Raises FileExistsError if already initialized (unless `exist_ok`).
        """
        ws = cls(root)
        if cls.is_workspace(ws.root):
            if not exist_ok:
                raise FileExistsError(f"{ws.root} is already a Cofound workspace.")
            return ws

        # Create the directory tree.
        (ws.root / DOCS_DIR).mkdir(parents=True, exist_ok=True)
        (ws.root / NOTES_DIR).mkdir(parents=True, exist_ok=True)
        (ws.root / COFOUND_DIR / LOG_DIR).mkdir(parents=True, exist_ok=True)

        # Seed machine state.
        save_config(ws.root, WorkspaceConfig(name=name))
        save_state(ws.root, WorkspaceState())

        # Seed an empty PLAN.md so the canvas pane has something to show until
        # Ultraplan writes the first real plan.
        if not ws.plan.exists():
            ws.plan.write(
                f"# {name} — Plan\n\n"
                "_No plan yet. Your cofounder will run Ultraplan once it "
                "understands the project._\n"
            )
        return ws

    @classmethod
    def open(cls, root: str | Path) -> "Workspace":
        """Open an existing workspace, validating it's initialized."""
        ws = cls(root)
        if not cls.is_workspace(ws.root):
            raise FileNotFoundError(
                f"{ws.root} is not a Cofound workspace. "
                "Create one with `cofound --new <path>`."
            )
        return ws

    # -- machine state ------------------------------------------------------

    @property
    def config(self) -> WorkspaceConfig:
        return load_config(self.root)

    def save_config(self, config: WorkspaceConfig) -> None:
        save_config(self.root, config)

    @property
    def state(self) -> WorkspaceState:
        return load_state(self.root)

    def save_state(self, state: WorkspaceState) -> None:
        save_state(self.root, state)

    @property
    def log_dir(self) -> Path:
        return self.root / COFOUND_DIR / LOG_DIR

    @property
    def state_file(self) -> Path:
        return state_path(self.root)

    # -- snapshot -----------------------------------------------------------

    def snapshot(self) -> str:
        """Return the full text of every human-facing canvas file.

        This is exactly what Ultraplan receives (canvas-only, no chat history).
        Order: PLAN.md first, then docs, then notes — each under a header that
        names its path so the planner can reference files precisely.
        """
        parts: list[str] = []

        if self.plan.exists():
            plan_text = self.plan.read().strip()
            if plan_text:
                parts.append(f"===== {PLAN_FILE} =====\n{plan_text}")

        for item in self.docs.read_all():
            parts.append(f"===== {DOCS_DIR}/{item.slug}.md =====\n{item.content.strip()}")

        for item in self.notes.read_all():
            parts.append(f"===== {NOTES_DIR}/{item.slug}.md =====\n{item.content.strip()}")

        if not parts:
            return "(The canvas is empty — no plan, documents, or notes yet.)"
        return "\n\n".join(parts) + "\n"

    def files(self) -> list[Path]:
        """All human-facing canvas files that currently exist, for the UI tree."""
        out: list[Path] = []
        if self.plan.exists():
            out.append(self.plan.path)
        out += [self.docs.path_for(s) for s in self.docs.list()]
        out += [self.notes.path_for(s) for s in self.notes.list()]
        return out
