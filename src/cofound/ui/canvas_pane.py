"""The canvas pane: a live view of the workspace files.

Left-to-right in the app this sits on the right. It shows a filtered file tree of
the workspace (PLAN.md, docs/, notes/) and a Markdown viewer that re-renders
whenever the selected file changes on disk — so the user *sees* the canvas update
as the cofounder writes to it.

File-change detection is a cheap mtime poll (no model involvement); CLAUDE.md only
forbids background polling of the *model*, not the filesystem.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import DirectoryTree, Markdown, Static


class CanvasTree(DirectoryTree):
    """A DirectoryTree that only shows human-facing canvas files."""

    _SKIP = {".cofound", ".venv", "dist", "build", "__pycache__", ".git", "node_modules"}

    def filter_paths(self, paths):
        out = []
        for p in paths:
            if p.name in self._SKIP or p.name.startswith("."):
                continue
            if p.is_dir() or p.suffix == ".md":
                out.append(p)
        return out


class CanvasPane(Vertical):
    """File tree + markdown viewer with live refresh."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = Path(root)
        self._current: Path | None = None
        self._mtimes: dict[str, float] = {}

    def compose(self) -> ComposeResult:
        yield Static("[b]canvas[/b]  [dim]— your workspace[/dim]", id="canvas-title")
        yield CanvasTree(str(self.root), id="canvas-tree")
        with VerticalScroll(id="canvas-view"):
            yield Markdown("", id="canvas-md")

    def on_mount(self) -> None:
        # Show PLAN.md first if it exists, else a hint.
        plan = self.root / "PLAN.md"
        if plan.exists():
            self.run_worker(self.show_path(plan), exclusive=False)
        else:
            self.run_worker(self._set_md("_Select a file from the tree._"), exclusive=False)
        self._mtimes = self._snapshot_mtimes()
        # Poll the filesystem for changes a couple of times a second.
        self.set_interval(0.7, self._poll)

    # -- viewer -------------------------------------------------------------

    async def _set_md(self, text: str) -> None:
        await self.query_one("#canvas-md", Markdown).update(text)

    async def show_path(self, path: Path) -> None:
        path = Path(path)
        if path.is_dir() or path.suffix != ".md":
            return
        self._current = path
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = "_(file removed)_"
        self.query_one("#canvas-title", Static).update(
            f"[b]canvas[/b]  [dim]— {path.name}[/dim]"
        )
        await self._set_md(text)

    @on(DirectoryTree.FileSelected)
    async def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        await self.show_path(event.path)

    # -- live refresh -------------------------------------------------------

    def _canvas_files(self) -> list[Path]:
        out: list[Path] = []
        plan = self.root / "PLAN.md"
        if plan.exists():
            out.append(plan)
        for sub in ("docs", "notes"):
            d = self.root / sub
            if d.is_dir():
                out.extend(sorted(d.glob("*.md")))
        return out

    def _snapshot_mtimes(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for p in self._canvas_files():
            try:
                snap[str(p)] = p.stat().st_mtime
            except OSError:
                pass
        return snap

    def _poll(self) -> None:
        current = self._snapshot_mtimes()
        if current == self._mtimes:
            return
        # The set of files or their contents changed.
        added_or_removed = set(current) != set(self._mtimes)
        self._mtimes = current

        if added_or_removed:
            tree = self.query_one("#canvas-tree", CanvasTree)
            self.run_worker(_reload_tree(tree), exclusive=False)

        # Re-render the open file if it changed (or open PLAN.md if nothing open).
        target = self._current or (self.root / "PLAN.md")
        if target and target.exists():
            self.run_worker(self.show_path(target), exclusive=False)

    def refresh_now(self) -> None:
        """Force an immediate refresh (e.g. right after a turn finishes)."""
        self._mtimes = {}
        self._poll()


async def _reload_tree(tree: CanvasTree) -> None:
    try:
        await tree.reload()
    except Exception:
        # Tree reload is best-effort; never let it crash the UI.
        pass
