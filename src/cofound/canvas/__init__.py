"""Canvas layer — typed read/write over the workspace files.

The filesystem is the shared state. Import everything you need from here.
"""

from .documents import Documents, MarkdownItem, MarkdownStore, slugify
from .notes import Notes
from .plan import Plan, Task
from .state import (
    WorkspaceConfig,
    WorkspaceState,
    load_config,
    load_state,
    save_config,
    save_state,
    utcnow_iso,
)
from .workspace import Workspace

__all__ = [
    "Workspace",
    "Documents",
    "Notes",
    "MarkdownStore",
    "MarkdownItem",
    "slugify",
    "Plan",
    "Task",
    "WorkspaceConfig",
    "WorkspaceState",
    "load_config",
    "save_config",
    "load_state",
    "save_state",
    "utcnow_iso",
]
