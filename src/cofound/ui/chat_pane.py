"""The chat pane: the conversation with your cofounder.

A scrollable log of message bubbles plus an input box. The app drives streaming:
it calls `begin_assistant()` to open a bubble, then `stream(delta)` repeatedly as
tokens arrive. Slash commands are recognized here and surfaced to the app via the
`Command` message.
"""

from __future__ import annotations

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static


class ChatMessage(Static):
    """One message bubble. `role` drives styling."""

    def __init__(self, role: str, text: str = "") -> None:
        super().__init__()
        self.role = role
        self._text = text
        self.add_class(f"role-{role}")

    def on_mount(self) -> None:
        self._refresh()

    def append(self, delta: str) -> None:
        self._text += delta
        self._refresh()

    def set_text(self, text: str) -> None:
        self._text = text
        self._refresh()

    @property
    def text(self) -> str:
        return self._text

    def _refresh(self) -> None:
        labels = {
            "you": "[b]you[/b]",
            "cofounder": "[b]cofounder[/b]",
            "system": "[dim]system[/dim]",
            "error": "[b red]error[/b red]",
        }
        label = labels.get(self.role, self.role)
        body = escape(self._text) if self.role in {"you", "error"} else self._text
        self.update(f"{label}\n{body}" if body else label)


class ChatPane(Vertical):
    """Conversation log + input box."""

    class Submitted(Message):
        """A plain chat message the user submitted (not a slash command)."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class Command(Message):
        """A slash command, e.g. '/ultraplan'. `name` excludes the slash."""

        def __init__(self, name: str, arg: str) -> None:
            super().__init__()
            self.name = name
            self.arg = arg

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
        yield Input(placeholder="Talk to your cofounder…  (/help for commands)", id="chat-input")

    # -- log helpers --------------------------------------------------------

    @property
    def _log(self) -> VerticalScroll:
        return self.query_one("#chat-log", VerticalScroll)

    async def _add(self, msg: ChatMessage) -> ChatMessage:
        await self._log.mount(msg)
        msg.scroll_visible()
        self._log.scroll_end(animate=False)
        return msg

    async def add_user(self, text: str) -> None:
        await self._add(ChatMessage("you", text))

    async def add_system(self, text: str) -> None:
        await self._add(ChatMessage("system", text))

    async def add_error(self, text: str) -> None:
        await self._add(ChatMessage("error", text))

    async def begin_assistant(self) -> ChatMessage:
        """Open an empty cofounder bubble to stream into."""
        return await self._add(ChatMessage("cofounder", ""))

    def stream(self, bubble: ChatMessage, delta: str) -> None:
        bubble.append(delta)
        self._log.scroll_end(animate=False)

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()

    # -- input handling -----------------------------------------------------

    @on(Input.Submitted, "#chat-input")
    def _handle_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            name = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            self.post_message(self.Command(name, arg))
        else:
            self.post_message(self.Submitted(text))
