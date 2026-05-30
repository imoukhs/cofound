"""`cofound` command-line entry point.

  cofound                 open the workspace in the current directory (creating
                          one here if needed) and launch the TUI
  cofound <path>          open/create a workspace at <path> and launch
  cofound --new <path>    create a new workspace at <path> and launch
  cofound doctor          no-cost check that Claude Code is installed + logged in
  cofound --version
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import __version__


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="cofound",
        description=(
            "An AI cofounder in your terminal. It leads the conversation, plans "
            "strategically, and writes everything to a local file-based canvas. "
            "Runs on your own Claude subscription login — built on Claude."
        ),
        epilog=(
            "Prerequisite: install Claude Code and run `claude` once to log in to "
            "your Pro/Max (or Team/Enterprise) plan. Cofound uses that login; it "
            "never needs an API key."
        ),
    )
    parser.add_argument("--version", action="version", version=f"cofound {__version__}")
    parser.add_argument(
        "--new", metavar="PATH", help="Create a new workspace at PATH and open it."
    )
    parser.add_argument(
        "--name", metavar="NAME", help="Name for a newly created workspace."
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        help="Path to a workspace to open (defaults to the current directory).",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "doctor",
        help="Check Claude Code is installed and you're logged in (no model call).",
    )
    return parser


def _cmd_doctor() -> int:
    from .engine import preflight

    status = preflight()
    ok, no = "✓", "✗"
    print("Cofound preflight\n")
    print(f"  {ok if status.sdk_importable else no} claude-agent-sdk importable")
    print(f"  {ok if status.has_oauth_creds else no} Claude login detected (subscription)")
    if status.has_api_key:
        print("  ! ANTHROPIC_API_KEY is set in your environment")
    print()
    print(status.detail)
    print()
    if status.likely_ready:
        print("Looks ready. (The only sure test is one real call — see the smoke test.)")
        return 0
    print("Not ready yet — fix the items marked ✗ above.")
    return 1


def _launch(target: Path, *, create: bool, name: str | None) -> int:
    """Open/create a workspace and run the TUI."""
    from .canvas import Workspace
    from .engine import preflight

    # Gate on the no-cost preflight so we fail loud, early, and actionably.
    status = preflight()
    if not status.likely_ready:
        print("Can't start Cofound yet:\n")
        print(status.detail)
        print("\nRun `cofound doctor` for details.")
        return 1

    if Workspace.is_workspace(target):
        ws = Workspace.open(target)
    elif create:
        ws_name = name or target.resolve().name or "Untitled"
        ws = Workspace.create(target, name=ws_name)
        print(f"Created a new workspace '{ws.config.name}' at {ws.root}")
    else:
        print(f"{target} is not a Cofound workspace. Create one with `cofound --new {target}`.")
        return 1

    # Import the app lazily so --version/doctor don't pull in Textual.
    from .ui import CofoundApp

    CofoundApp(ws).run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _cmd_doctor()

    if args.new:
        return _launch(Path(args.new), create=True, name=args.name)

    target = Path(args.workspace) if args.workspace else Path.cwd()
    # Opening a path that isn't yet a workspace will create it (single-user, local).
    return _launch(target, create=True, name=args.name)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
