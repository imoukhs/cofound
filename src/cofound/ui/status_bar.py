"""The footer status bar: session, phase, working state, and usage/cost.

Purely presentational — the app pushes state into it via `update(...)`.
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Static):
    """A single-line footer summarizing session + activity + usage."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
    }
    """

    phase: reactive[str] = reactive("onboarding")
    session_id: reactive[str | None] = reactive(None)
    activity: reactive[str] = reactive("ready")
    cost_usd: reactive[float | None] = reactive(None)

    def _render_line(self) -> str:
        sid = self.session_id
        sid_disp = (sid[:8] + "…") if sid and len(sid) > 9 else (sid or "—")
        cost = f"${self.cost_usd:.4f}" if self.cost_usd is not None else "—"
        # Rich markup for a little polish.
        return (
            f"[b]●[/b] {self.activity}"
            f"  [dim]│[/dim]  phase [b]{self.phase}[/b]"
            f"  [dim]│[/dim]  session [b]{sid_disp}[/b]"
            f"  [dim]│[/dim]  cost [b]{cost}[/b]"
            f"  [dim]│[/dim]  [dim]/help[/dim]"
        )

    def watch_phase(self) -> None:
        self.update(self._render_line())

    def watch_session_id(self) -> None:
        self.update(self._render_line())

    def watch_activity(self) -> None:
        self.update(self._render_line())

    def watch_cost_usd(self) -> None:
        self.update(self._render_line())

    def on_mount(self) -> None:
        self.update(self._render_line())

    # Convenience setters used by the app.
    def set_working(self, what: str) -> None:
        self.activity = f"[yellow]{what}[/yellow]"

    def set_idle(self) -> None:
        self.activity = "[green]ready[/green]"

    def set_error(self) -> None:
        self.activity = "[red]error[/red]"
