"""CRUD for `notes/*.md` — short standalone notes.

Same storage model as documents (see `documents.MarkdownStore`); notes are just
the `notes/` directory and are meant to be brief.
"""

from __future__ import annotations

from .documents import MarkdownStore


class Notes(MarkdownStore):
    """The `notes/` directory."""

    kind = "note"
