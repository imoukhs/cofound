"""Workspace / documents / notes / plan CRUD and snapshot.

No real model calls anywhere in here.
"""

from __future__ import annotations

import pytest

from cofound.canvas import Workspace, slugify
from cofound.canvas.state import COFOUND_DIR


# --- workspace lifecycle ----------------------------------------------------


def test_create_scaffolds_layout(tmp_path):
    ws = Workspace.create(tmp_path / "proj", name="My Startup")
    assert (ws.root / "docs").is_dir()
    assert (ws.root / "notes").is_dir()
    assert (ws.root / COFOUND_DIR / "log").is_dir()
    assert (ws.root / COFOUND_DIR / "config.json").exists()
    assert (ws.root / COFOUND_DIR / "state.json").exists()
    assert ws.plan.exists()
    assert ws.config.name == "My Startup"
    assert Workspace.is_workspace(ws.root)


def test_create_twice_raises_unless_exist_ok(tmp_path):
    Workspace.create(tmp_path / "p", name="A")
    with pytest.raises(FileExistsError):
        Workspace.create(tmp_path / "p", name="A")
    # exist_ok returns the existing one.
    ws = Workspace.create(tmp_path / "p", name="A", exist_ok=True)
    assert ws.config.name == "A"


def test_open_requires_initialized(tmp_path):
    with pytest.raises(FileNotFoundError):
        Workspace.open(tmp_path / "empty")
    Workspace.create(tmp_path / "ok", name="Z")
    assert Workspace.open(tmp_path / "ok").config.name == "Z"


# --- documents / notes ------------------------------------------------------


def test_slugify():
    assert slugify("Target Customer") == "target-customer"
    assert slugify("  Pricing & Packaging!! ") == "pricing-packaging"
    assert slugify("") == "untitled"


def test_documents_crud(workspace):
    docs = workspace.docs
    assert docs.list() == []

    item = docs.write("Target Customer", "They are SMB founders.")
    # Title falls back to the slug-derived name, and an H1 was prepended.
    assert item.slug == "target-customer"
    assert item.title == "Target Customer"
    assert item.content.startswith("# Target Customer")
    assert "SMB founders" in item.content

    assert docs.exists("Target Customer")
    assert docs.list() == ["target-customer"]

    # Read by slug or title (both slugify the same).
    assert docs.read("target-customer").content == item.content
    assert docs.read("Target Customer").content == item.content

    # Append.
    docs.append("Target Customer", "Also: design-conscious.")
    assert "design-conscious" in docs.read("target-customer").content

    # Overwrite.
    docs.write("target-customer", "# Target Customer\n\nReplaced.")
    assert docs.read("target-customer").content.strip().endswith("Replaced.")

    # Delete.
    assert docs.delete("target-customer") is True
    assert docs.delete("target-customer") is False
    assert docs.list() == []


def test_title_from_h1_is_preserved(workspace):
    item = workspace.docs.write("notes-slug", "# A Custom Title\n\nbody")
    assert item.title == "A Custom Title"
    # Existing H1 means we don't prepend another.
    assert item.content.count("# A Custom Title") == 1


def test_notes_are_independent_of_docs(workspace):
    workspace.notes.write("idea", "quick thought")
    assert workspace.notes.list() == ["idea"]
    assert workspace.docs.list() == []  # separate directories


def test_read_missing_raises(workspace):
    with pytest.raises(FileNotFoundError):
        workspace.docs.read("does-not-exist")


# --- plan -------------------------------------------------------------------


PLAN_SAMPLE = """# Plan

## Phase 1
- [ ] Define the problem
- [ ] Talk to 5 users
- [x] Pick a name

Some prose.
- not a task
"""


def test_plan_tasks_parsing(workspace):
    workspace.plan.write(PLAN_SAMPLE)
    tasks = workspace.plan.tasks()
    assert [t.text for t in tasks] == [
        "Define the problem",
        "Talk to 5 users",
        "Pick a name",
    ]
    assert [t.done for t in tasks] == [False, False, True]
    assert workspace.plan.progress() == (1, 3)


def test_plan_check_off(workspace):
    workspace.plan.write(PLAN_SAMPLE)
    assert workspace.plan.check_off("talk to 5 users") is True  # case-insensitive
    tasks = {t.text: t.done for t in workspace.plan.tasks()}
    assert tasks["Talk to 5 users"] is True
    # Unchecking works too.
    assert workspace.plan.check_off("Pick a name", done=False) is True
    assert {t.text: t.done for t in workspace.plan.tasks()}["Pick a name"] is False
    # No match returns False.
    assert workspace.plan.check_off("nonexistent task") is False


def test_plan_toggle_by_line(workspace):
    workspace.plan.write(PLAN_SAMPLE)
    first = workspace.plan.tasks()[0]
    assert first.done is False
    assert workspace.plan.toggle(first.line_no) is True
    assert workspace.plan.tasks()[0].done is True


# --- snapshot ---------------------------------------------------------------


def test_snapshot_empty_workspace(workspace):
    # A fresh workspace has a seeded PLAN.md but no docs/notes.
    snap = workspace.snapshot()
    assert "PLAN.md" in snap
    assert "No plan yet" in snap


def test_snapshot_includes_all_canvas_text_in_order(workspace):
    workspace.plan.write("# The Plan\n\n- [ ] do it\n")
    workspace.docs.write("Vision", "We will win.")
    workspace.notes.write("idea", "a small note")

    snap = workspace.snapshot()
    # Headers name the file paths.
    assert "===== PLAN.md =====" in snap
    assert "===== docs/vision.md =====" in snap
    assert "===== notes/idea.md =====" in snap
    # Ordering: plan before docs before notes.
    assert snap.index("PLAN.md") < snap.index("docs/vision.md") < snap.index("notes/idea.md")
    # Content present.
    assert "We will win." in snap
    assert "a small note" in snap


def test_files_lists_existing_canvas_files(workspace):
    workspace.docs.write("a", "x")
    workspace.notes.write("b", "y")
    names = {p.name for p in workspace.files()}
    assert "PLAN.md" in names
    assert "a.md" in names
    assert "b.md" in names
