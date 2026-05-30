#!/usr/bin/env python3
"""Throwaway smoke test — confirm the engine reaches your Claude subscription.

This makes EXACTLY ONE cheap model call (no tools, tiny prompt) so you can
verify auth + streaming before we build anything else. Delete it whenever.

Run it (from the repo root, after `uv sync`):

    uv run python smoke_test.py

What it does:
  1. Runs the no-cost preflight (checks SDK import + login presence).
  2. Asks the model to reply with a single short word.
  3. Prints the reply, the session id (proves session continuity works), and
     any usage/cost the SDK reports.

It deliberately does NOT use an API key. If you're not logged in, it prints an
actionable message instead of a stack trace.
"""

from __future__ import annotations

import asyncio

from cofound.engine import (
    CofoundEngineError,
    DoneEvent,
    Engine,
    TextEvent,
    preflight,
)


async def main() -> int:
    print("== Preflight (no model call) ==")
    status = preflight()
    print(f"  sdk importable     : {status.sdk_importable}")
    print(f"  login detected     : {status.has_oauth_creds}")
    print(f"  ANTHROPIC_API_KEY  : {'set (note: not used by design)' if status.has_api_key else 'unset (good)'}")
    print(f"  -> {status.detail}\n")

    if not status.sdk_importable:
        print("Cannot continue: the SDK isn't importable. Run `uv sync`.")
        return 1

    print("== One cheap call ==")
    engine = Engine()
    reply: list[str] = []
    try:
        async for event in engine.ask(
            "Reply with exactly one word: ready",
            system="You are a terse assistant. Answer in one word.",
            tools=[],  # no tools — keeps it cheap and safe
        ):
            if isinstance(event, TextEvent):
                reply.append(event.text)
                print(event.text, end="", flush=True)
            elif isinstance(event, DoneEvent):
                print("\n")
                print("== Result ==")
                print(f"  session id : {event.session_id}")
                print(f"  turns      : {event.num_turns}")
                print(f"  cost (usd) : {event.total_cost_usd}")
                print(f"  usage      : {event.usage}")
    except CofoundEngineError as exc:
        print("\n\nThe call failed:\n")
        print(exc)
        return 1

    text = "".join(reply).strip()
    print()
    if text:
        print(f"Success — the engine talked to your subscription. (\"{text}\")")
        print(f"Session continuity works: pass session id {engine.last_session_id!r} as `resume`.")
        return 0
    print("The call returned no text. Check the result block above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
