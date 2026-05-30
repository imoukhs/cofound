"""CRUD for `docs/*.md` — the documents the cofounder writes.

A document is just a Markdown file. We address them by a URL-safe *slug* derived
from a title, so the cofounder can say "write the doc 'Target Customer'" and we
map that to `docs/target-customer.md`.

`MarkdownStore` is the shared base used by both documents and notes (see
`notes.py`); keeping it here avoids a third helper module.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from .state import atomic_write_text

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def slugify(text: str) -> str:
    """Turn a title into a safe, lowercase, hyphenated filename stem."""
    slug = _SLUG_STRIP.sub("-", text.strip().lower()).strip("-")
    return slug or "untitled"


def _title_from(content: str, fallback: str) -> str:
    """Use the first H1 as the title, else a humanized fallback (the slug)."""
    match = _H1.search(content)
    if match:
        return match.group(1).strip()
    return fallback.replace("-", " ").title()


class MarkdownItem(BaseModel):
    """An in-memory view of one markdown file on the canvas."""

    slug: str
    title: str
    content: str
    path: Path

    model_config = {"arbitrary_types_allowed": True}


class MarkdownStore:
    """A flat directory of `*.md` files addressed by slug."""

    #: Subclasses set this to the canvas sub-directory name they manage.
    kind: str = "item"

    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    # -- paths --------------------------------------------------------------

    def path_for(self, slug: str) -> Path:
        return self.dir / f"{slugify(slug)}.md"

    # -- queries ------------------------------------------------------------

    def exists(self, slug: str) -> bool:
        return self.path_for(slug).exists()

    def list(self) -> list[str]:
        """Slugs of all items, sorted."""
        if not self.dir.exists():
            return []
        return sorted(p.stem for p in self.dir.glob("*.md"))

    def read(self, slug: str) -> MarkdownItem:
        path = self.path_for(slug)
        if not path.exists():
            raise FileNotFoundError(f"No {self.kind} named {slug!r} in {self.dir}")
        content = path.read_text(encoding="utf-8")
        norm = slugify(slug)
        return MarkdownItem(
            slug=norm,
            title=_title_from(content, norm),
            content=content,
            path=path,
        )

    def read_all(self) -> list[MarkdownItem]:
        return [self.read(slug) for slug in self.list()]

    # -- mutations ----------------------------------------------------------

    def write(self, slug: str, content: str, *, title: str | None = None) -> MarkdownItem:
        """Create or overwrite an item.

        If the content has no leading H1, we prepend one (the explicit `title`,
        or a humanized version of the slug) so every canvas file is
        self-describing on disk and renders with a heading in the viewer.
        """
        norm = slugify(slug)
        body = content
        if not _H1.search(content):
            heading = title or _title_from("", norm)
            body = f"# {heading}\n\n{content}"
        path = self.path_for(norm)
        atomic_write_text(path, body if body.endswith("\n") else body + "\n")
        return self.read(norm)

    def append(self, slug: str, content: str) -> MarkdownItem:
        """Append content to an existing item (or create it if missing)."""
        existing = self.read(slug).content if self.exists(slug) else ""
        sep = "" if not existing or existing.endswith("\n\n") else (
            "\n" if existing.endswith("\n") else "\n\n"
        )
        return self.write(slug, existing + sep + content)

    def delete(self, slug: str) -> bool:
        path = self.path_for(slug)
        if path.exists():
            path.unlink()
            return True
        return False


class Documents(MarkdownStore):
    """The `docs/` directory."""

    kind = "document"
