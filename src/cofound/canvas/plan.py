"""`PLAN.md` — the living plan document.

Ultraplan owns the *structure* of this file (objective, phased tasks, criteria).
The chat cofounder may *check off* tasks as they're completed, which is what the
`Task` parsing and `check_off` / `toggle` helpers here support.

We treat PLAN.md as Markdown with GitHub-style task list items:

    - [ ] An open task
    - [x] A completed task
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from .state import atomic_write_text

# Matches a task list line, capturing indentation, the check state, and text.
_TASK_RE = re.compile(r"^(?P<indent>\s*)[-*]\s+\[(?P<mark>[ xX])\]\s+(?P<text>.*\S)\s*$")


class Task(BaseModel):
    """One checkbox item in PLAN.md."""

    line_no: int  # zero-based index into the file's lines
    text: str
    done: bool


class Plan:
    """Read/write access to a workspace's PLAN.md."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    # -- raw content --------------------------------------------------------

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def write(self, content: str) -> None:
        atomic_write_text(self.path, content if content.endswith("\n") else content + "\n")

    # -- tasks --------------------------------------------------------------

    def tasks(self) -> list[Task]:
        """All checkbox tasks, in document order."""
        out: list[Task] = []
        for i, line in enumerate(self.read().splitlines()):
            m = _TASK_RE.match(line)
            if m:
                out.append(
                    Task(
                        line_no=i,
                        text=m.group("text"),
                        done=m.group("mark").lower() == "x",
                    )
                )
        return out

    def _set_line_mark(self, line_no: int, done: bool) -> bool:
        lines = self.read().splitlines()
        if not (0 <= line_no < len(lines)):
            return False
        m = _TASK_RE.match(lines[line_no])
        if not m:
            return False
        mark = "x" if done else " "
        lines[line_no] = f"{m.group('indent')}- [{mark}] {m.group('text')}"
        self.write("\n".join(lines))
        return True

    def check_off(self, text: str, *, done: bool = True) -> bool:
        """Check (or uncheck) the first task whose text matches `text`.

        Matching is case-insensitive and substring-based so the cofounder can
        refer to a task without quoting it verbatim. Returns True if a task was
        changed.
        """
        needle = text.strip().lower()
        for task in self.tasks():
            if needle in task.text.lower():
                return self._set_line_mark(task.line_no, done)
        return False

    def toggle(self, line_no: int) -> bool:
        """Flip the checkbox on a specific line. Returns True if changed."""
        for task in self.tasks():
            if task.line_no == line_no:
                return self._set_line_mark(line_no, not task.done)
        return False

    def progress(self) -> tuple[int, int]:
        """(#done, #total) across all tasks."""
        tasks = self.tasks()
        return sum(1 for t in tasks if t.done), len(tasks)
