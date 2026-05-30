"""Typed engine errors.

These are the *only* errors the rest of Cofound should have to reason about.
The engine translates raw Claude Agent SDK exceptions into these, so no other
module needs to know the SDK's exception taxonomy.

Design goals (per CLAUDE.md):
  - Fail loud on auth/credit problems with a clear, actionable message.
  - Keep all SDK-specific knowledge inside `engine/`.
"""

from __future__ import annotations


class CofoundEngineError(Exception):
    """Base class for every error surfaced by the engine.

    Carries a human-facing, actionable `message` and an optional `detail`
    (usually raw stderr) for logs.
    """

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.detail:
            return f"{self.message}\n\n  details: {self.detail}"
        return self.message


class CLINotInstalled(CofoundEngineError):
    """The Claude Code CLI backing the Agent SDK could not be found."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            "Claude Code isn't installed (or couldn't be located).\n"
            "Install it and sign in, then try again:\n"
            "  1. Install Claude Code (https://claude.com/code)\n"
            "  2. Run `claude` once and log in to your Pro/Max plan.",
            detail=detail,
        )


class AuthMissing(CofoundEngineError):
    """No usable subscription login was found.

    Cofound uses your *own* Claude subscription login (the OAuth credential
    created by running `claude` / `claude login`). It deliberately does not use
    an API key.
    """

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            "You're not logged in to Claude.\n"
            "Cofound runs on your own Claude subscription, so it needs you to "
            "sign in once:\n"
            "  1. Run `claude` in a terminal.\n"
            "  2. Log in to your Pro/Max (or Team/Enterprise) plan.\n"
            "Then restart Cofound.",
            detail=detail,
        )


class CreditExhausted(CofoundEngineError):
    """Subscription rate limit hit or the Agent SDK credit is used up."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            "Claude is out of capacity for now.\n"
            "This usually means your plan's rate limit or monthly Agent SDK "
            "credit is temporarily exhausted. Wait for it to refresh, or use a "
            "higher plan, then try again.",
            detail=detail,
        )


class EngineFailure(CofoundEngineError):
    """A model call failed for a reason we couldn't classify more precisely."""


# --- classification helpers -------------------------------------------------

# Substrings we treat as auth problems (case-insensitive match against stderr
# / error text). Kept here so the matching logic lives in one place.
_AUTH_SIGNS = (
    "not logged in",
    "please log in",
    "log in to",
    "login required",
    "unauthorized",
    "authentication",
    "no credentials",
    "invalid api key",
    "oauth",
    "401",
    "403",
)

_CREDIT_SIGNS = (
    "rate limit",
    "rate-limit",
    "rate_limit",
    "quota",
    "credit",
    "usage limit",
    "overloaded",
    "429",
    "exceeded",
)


def _haystack(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).lower()


def classify_sdk_error(exc: Exception) -> CofoundEngineError:
    """Translate a raw SDK/runtime exception into a typed engine error.

    The SDK raises a small family of exceptions (CLINotFoundError, ProcessError,
    CLIConnectionError, ...). We import them lazily so this module stays
    importable even if the SDK isn't installed (e.g. in unit tests).
    """
    # Already one of ours — pass through unchanged.
    if isinstance(exc, CofoundEngineError):
        return exc

    name = type(exc).__name__
    message = str(exc)
    stderr = getattr(exc, "stderr", None)
    text = _haystack(message, stderr)

    if name == "CLINotFoundError":
        return CLINotInstalled(detail=getattr(exc, "cli_path", None) or message)

    if any(sign in text for sign in _CREDIT_SIGNS):
        return CreditExhausted(detail=stderr or message)

    if any(sign in text for sign in _AUTH_SIGNS):
        return AuthMissing(detail=stderr or message)

    # ProcessError with a nonzero exit and empty/uninformative stderr most
    # often means the CLI refused to start a session — frequently auth.
    if name in {"ProcessError", "CLIConnectionError"} and not text.strip():
        return AuthMissing(detail=stderr or message)

    return EngineFailure(
        f"The model call failed ({name}).", detail=stderr or message or None
    )
