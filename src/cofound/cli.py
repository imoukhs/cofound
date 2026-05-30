"""`cofound` command-line entry point.

For STEP 1 this provides:
  - `cofound --version` / `--help`
  - `cofound doctor` — a no-cost preflight that checks SDK + login presence.

Workspace creation (`--new`) and launching the TUI are wired up in later steps;
they print a clear "coming in a later step" message for now so the entry point
is always runnable.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cofound",
        description=(
            "An AI cofounder in your terminal. It leads the conversation, plans "
            "strategically, and writes everything to a local file-based canvas. "
            "Runs on your own Claude subscription login — built on Claude."
        ),
        epilog=(
            "Prerequisite: install Claude Code and run `claude` once to log in "
            "to your Pro/Max (or Team/Enterprise) plan. Cofound uses that login; "
            "it never needs an API key."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"cofound {__version__}"
    )
    parser.add_argument(
        "--new",
        metavar="PATH",
        help="Create a new workspace at PATH and open it (coming in a later step).",
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        help="Path to an existing workspace to open (defaults to the current directory).",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "doctor",
        help="Check that Claude Code is installed and you're logged in (no model call).",
    )
    return parser


def _cmd_doctor() -> int:
    """Run the no-cost preflight and print an actionable report."""
    from .engine import preflight

    status = preflight()
    ok = "✓"
    no = "✗"

    print("Cofound preflight\n")
    print(f"  {ok if status.sdk_importable else no} claude-agent-sdk importable")
    print(f"  {ok if status.has_oauth_creds else no} Claude login detected (subscription)")
    if status.has_api_key:
        print(f"  ! ANTHROPIC_API_KEY is set in your environment")
    print()
    print(status.detail)
    print()

    if status.likely_ready:
        print("Looks ready. (The only sure test is one real call — see the smoke test.)")
        return 0
    print("Not ready yet — fix the items marked ✗ above.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _cmd_doctor()

    if args.new:
        print(
            "Workspace creation isn't wired up yet (arrives with the canvas + "
            "UI steps). For now, run `cofound doctor` to verify your setup."
        )
        return 0

    # Default: would launch the TUI. The UI lands in a later step.
    print(
        "The Cofound TUI isn't wired up yet — it arrives in the UI step.\n"
        "Run `cofound doctor` to check your environment, or `cofound --help`."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
