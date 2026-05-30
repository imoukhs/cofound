"""Version-controlled system prompts + prompt assembly.

The raw persona/planner text lives in `cofounder.md` and `ultraplan.md` alongside
this module. Loaders read them as package data so they ship in the wheel.

Prompt *assembly* is deliberately a function, not a constant: per the "richer
onboarding" direction in CLAUDE.md, persona tone and canvas-write behaviour are
**inputs** to the system prompt, so a future onboarding can set them without
touching the base prompt. v1 just uses the defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


def load_prompt(name: str) -> str:
    """Return the raw text of `prompts/<name>.md`."""
    return (files(__package__) / f"{name}.md").read_text(encoding="utf-8")


# --- preferences seam -------------------------------------------------------


@dataclass(frozen=True)
class CofounderPrefs:
    """User preferences that shape how the cofounder behaves.

    Defaults match the persona we locked for v1 (warm-but-honest, auto-write).
    A later onboarding flow will populate these from the user and persist them.
    """

    # "warm_honest" | "sharper" | "gentler"
    tone: str = "warm_honest"
    # "auto_write" (write then tell) | "ask_first"
    write_behaviour: str = "auto_write"


_TONE_NOTE = {
    "warm_honest": (
        "Tone: warm but honest. You're on the user's side, which is exactly why "
        "you tell them the uncomfortable thing. Challenge respectfully; never "
        "flatter."
    ),
    "sharper": (
        "Tone: sharp and contrarian. Default to treating ideas as unproven until "
        "evidence shows otherwise. Apply real friction and push back hard — the "
        "user has chosen this mode and wants it."
    ),
    "gentler": (
        "Tone: gentle and supportive. Stay honest, but lead with encouragement "
        "and raise challenges diplomatically."
    ),
}

_WRITE_NOTE = {
    "auto_write": (
        "Canvas writes: when a decision is reached, capture it to the canvas "
        "immediately, then briefly tell the user where you wrote it."
    ),
    "ask_first": (
        "Canvas writes: before writing a document, briefly propose it and wait "
        "for the user's go-ahead. Don't write to docs/ without confirmation."
    ),
}


def build_cofounder_system(prefs: CofounderPrefs | None = None) -> str:
    """Assemble the cofounder system prompt: base persona + preference overrides."""
    prefs = prefs or CofounderPrefs()
    base = load_prompt("cofounder")
    overrides = "\n".join(
        [
            "## Active preferences",
            "",
            _TONE_NOTE.get(prefs.tone, _TONE_NOTE["warm_honest"]),
            "",
            _WRITE_NOTE.get(prefs.write_behaviour, _WRITE_NOTE["auto_write"]),
        ]
    )
    return f"{base.rstrip()}\n\n---\n\n{overrides}\n"


def build_ultraplan_system() -> str:
    """The Ultraplan system prompt (no user-tunable knobs in v1)."""
    return load_prompt("ultraplan")


__all__ = [
    "load_prompt",
    "CofounderPrefs",
    "build_cofounder_system",
    "build_ultraplan_system",
]
