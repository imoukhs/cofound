"""The Cofound Textual app: chat + live canvas, wired to the engine.

Layout: a header, a two-pane body (chat left, canvas right), and a status bar.
The chat drives the engine (cofounder persona); the canvas pane re-renders as the
cofounder writes files. Ultraplan and the first-run flow are filled in STEP 5 via
the hooks left here.
"""

from __future__ import annotations

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header

from ..canvas import Workspace
from ..engine import (
    CofoundEngineError,
    DoneEvent,
    Engine,
    TextEvent,
    ToolEvent,
)
from ..prompts import CofounderPrefs, build_cofounder_system
from .canvas_pane import CanvasPane
from .chat_pane import ChatPane
from .status_bar import StatusBar

COFOUNDER_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]

HELP_TEXT = """[b]Commands[/b]
  [b]/ultraplan[/b] [dim][why][/dim]   step back and (re)write PLAN.md
  [b]/canvas[/b]            jump focus to the canvas file tree
  [b]/new[/b]               start a new workspace
  [b]/help[/b]              show this help
  [b]/quit[/b]              exit

[b]Keys[/b]
  [b]ctrl+q[/b] quit   ·   [b]tab[/b] move focus   ·   [b]ctrl+p[/b] command palette

Just type to talk to your cofounder. It leads, challenges your assumptions, and
writes durable decisions to the canvas on the right."""


class CofoundApp(App):
    """The terminal app where you work with your AI cofounder."""

    CSS_PATH = "styles.css"
    TITLE = "Cofound"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "focus_canvas", "Canvas"),
        Binding("ctrl+l", "focus_input", "Chat"),
    ]

    def __init__(
        self,
        workspace: Workspace,
        *,
        engine: Engine | None = None,
        prefs: CofounderPrefs | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.engine = engine or Engine(default_cwd=workspace.root)
        self.prefs = prefs or CofounderPrefs()
        self._system_prompt = build_cofounder_system(self.prefs)
        self._busy = False
        self._cost: float | None = None

    # -- composition --------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main"):
            yield ChatPane(id="chat")
            yield CanvasPane(self.workspace.root)
        yield StatusBar()

    def on_mount(self) -> None:
        self.sub_title = self.workspace.config.name
        state = self.workspace.state
        status = self.query_one(StatusBar)
        status.phase = state.phase
        # Resume the prior chat session across restarts, if any.
        if state.session_id:
            self.engine.last_session_id = state.session_id
            status.session_id = state.session_id
        status.set_idle()
        self.query_one(ChatPane).focus_input()

    # -- actions ------------------------------------------------------------

    def action_focus_canvas(self) -> None:
        self.query_one(CanvasPane).query_one("#canvas-tree").focus()

    def action_focus_input(self) -> None:
        self.query_one(ChatPane).focus_input()

    # -- message handlers ---------------------------------------------------

    @on(ChatPane.Submitted)
    def _on_user_text(self, msg: ChatPane.Submitted) -> None:
        if self._busy:
            self.run_worker(
                self.query_one(ChatPane).add_system("…still working on the last turn."),
                exclusive=False,
            )
            return
        self._run_turn(msg.text)

    @on(ChatPane.Command)
    async def _on_command(self, msg: ChatPane.Command) -> None:
        chat = self.query_one(ChatPane)
        name = msg.name
        if name in {"quit", "q", "exit"}:
            self.exit()
        elif name == "help":
            await chat.add_system(HELP_TEXT)
        elif name == "canvas":
            self.action_focus_canvas()
        elif name == "new":
            await chat.add_system(
                "Creating a new workspace from inside the app arrives in STEP 5. "
                "For now, exit and run `cofound --new <path>`."
            )
        elif name == "ultraplan":
            await self.run_ultraplan(msg.arg or "user requested /ultraplan")
        else:
            await chat.add_system(f"Unknown command [b]/{name}[/b]. Try [b]/help[/b].")

    # -- the core turn ------------------------------------------------------

    @work(group="turn")
    async def _run_turn(self, text: str) -> None:
        chat = self.query_one(ChatPane)
        status = self.query_one(StatusBar)
        canvas = self.query_one(CanvasPane)

        self._busy = True
        await chat.add_user(text)
        bubble = await chat.begin_assistant()
        status.set_working("thinking…")
        got_text = False
        try:
            async for ev in self.engine.ask(
                text,
                system=self._system_prompt,
                tools=COFOUNDER_TOOLS,
                cwd=self.workspace.root,
            ):
                if isinstance(ev, TextEvent):
                    got_text = True
                    chat.stream(bubble, ev.text)
                elif isinstance(ev, ToolEvent):
                    status.set_working(ev.summary or ev.name)
                    canvas.refresh_now()
                elif isinstance(ev, DoneEvent):
                    self._persist_done(ev)
        except CofoundEngineError as exc:
            await chat.add_error(str(exc))
            status.set_error()
            return
        finally:
            self._busy = False
            canvas.refresh_now()

        if not got_text:
            bubble.set_text("[dim](no text returned)[/dim]")
        status.set_idle()

    def _persist_done(self, ev: DoneEvent) -> None:
        status = self.query_one(StatusBar)
        if ev.session_id:
            state = self.workspace.state
            state.session_id = ev.session_id
            self.workspace.save_state(state)
            status.session_id = ev.session_id
        if ev.total_cost_usd is not None:
            self._cost = (self._cost or 0.0) + ev.total_cost_usd
            status.cost_usd = self._cost

    # -- Ultraplan hook (filled in STEP 5) ----------------------------------

    async def run_ultraplan(self, why: str) -> None:
        """Placeholder until STEP 5 wires the isolated planning agent."""
        await self.query_one(ChatPane).add_system(
            "Ultraplan (isolated planning over the canvas) is wired in STEP 5."
        )
