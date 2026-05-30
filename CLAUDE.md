# Cofound

> An AI cofounder in your terminal. It thinks problems through with you, plans strategically,
> captures everything to a persistent local workspace, and drives the project forward.
> Inspired by the structure of aicofounder.com, rebuilt as a local, single-user TUI that runs
> on your own Claude subscription. Built on Claude.

This file is the project's operating memory. Read it at the start of every session.

---

## Prime directive

Build a **polished terminal app** where a user works with an AI cofounder. The cofounder
**leads** the conversation, **challenges assumptions**, and writes durable knowledge to a
**file-based canvas**. A separate planning agent (**Ultraplan**) periodically steps back and
re-plans. The chat is transient; the canvas is permanent.

Ship a small, correct, runnable core first. Improve along the way.

---

## Non-negotiable constraints

1. **Subscription auth only.** The app runs against the *user's own* logged-in Claude
   subscription (the OAuth credential created by running `claude` / `claude login`
   interactively). It must work for a user who has **no `ANTHROPIC_API_KEY`**.
   - Do **not** require or read `ANTHROPIC_API_KEY`.
   - Do **not** use Claude Code's `--bare` mode — bare mode skips the OAuth keychain and
     *requires* an API key, which defeats the purpose.
   - If auth is missing, the app should detect it and tell the user to run `claude` and log in.

2. **Local, single-user, per-machine.** Each user installs and runs it on their own device
   with their own login. There is **no central server** and **no shared/pooled subscription**.
   (Pooling a single subscription to serve many users is not permitted and is out of scope.)

3. **Credit-aware.** As of the official docs (verify at build time), Agent-SDK / `claude -p`
   usage on a subscription draws from a **separate monthly Agent SDK credit** (Pro ~$20,
   Max 5x ~$100, Max 20x ~$200/mo), refreshing each cycle, not pooled across users. Treat
   AI calls as a metered resource: no needless calls, no background polling of the model,
   and gate any future high-cost feature (e.g. Research) behind explicit user approval.
   Source to re-verify: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan

4. **Swappable engine.** All model calls go through one engine module. Nothing else in the
   codebase calls the SDK directly. This lets us change SDK/model/auth in one place.

---

## Tech stack

- **Language:** Python 3.12+
- **TUI:** [Textual](https://textual.textualize.io/) (+ Rich)
- **Engine:** the official **Claude Agent SDK for Python** (it wraps the Claude Code harness
  and can authenticate with the user's subscription). Confirm the exact package name, import
  path, and the precise call that uses *subscription* auth (not API key) against the current
  official Agent SDK docs before writing the engine — do not assume from memory.
  - Agent SDK docs: https://code.claude.com/docs/en/agent-sdk/overview
  - Headless/CLI reference: https://code.claude.com/docs/en/headless
- **Config/state:** plain JSON + Markdown files. Use `pydantic` for typed models.
- **Packaging:** a `cofound` console entry point. Use `uv` (preferred) or a venv.

Keep dependencies minimal. Justify any addition beyond the above.

---

## The canvas (file-based workspace)

The canvas is just a project directory. The filesystem *is* the shared state that every
agent reads from and writes to. One workspace = one product/project.

```
<workspace>/
  PLAN.md              # the living plan document (Ultraplan owns this)
  docs/                # documents the cofounder writes (markdown, one file per topic)
  notes/               # short standalone notes (markdown)
  .cofound/
    config.json        # workspace settings
    state.json         # current chat session id, phase, last-plan timestamp
    log/               # transcripts / debug logs
```

Rules:
- Everything the cofounder learns or decides gets written to `docs/` or `notes/`, not left
  only in chat. When a decision is reached in conversation, persist it.
- `PLAN.md` is special and is written by Ultraplan (see below). The chat cofounder may check
  off tasks in it as they're completed, but structural re-planning is Ultraplan's job.
- Markdown only for human-facing content. JSON only for machine state.

---

## Components (build in this order)

1. **Engine** (`engine/`): the single chokepoint for model calls.
   - `ask(messages, system, tools) -> stream of events` with subscription auth.
   - Maintains/returns a session id so conversations can be resumed across turns.
   - Surfaces token/credit usage from the SDK response when available, for display.
   - Handles auth-missing and rate-limit/credit-exhausted errors gracefully.

2. **Canvas layer** (`canvas/`): typed read/write over the workspace files above.
   - Create/update/read/list documents and notes; read/write `PLAN.md`; load/save state.
   - A `canvas.snapshot()` that returns the full text of all canvas files — this is what
     gets fed to Ultraplan.

3. **System prompts** (`prompts/`): version-controlled markdown.
   - `cofounder.md`: the persona — leads, asks one focused question at a time during
     context-gathering, challenges weak assumptions, prefers researching/verifying over
     guessing, and writes outcomes to the canvas. A thinking partner, not an order-taker.
   - `ultraplan.md`: constraint-focused planning (see below).

4. **TUI** (`ui/`): a Textual app with two panes.
   - **Chat pane** (left): the conversation; streams the cofounder's responses; shows status
     while it's working ("writing to canvas...", "planning...").
   - **Canvas pane** (right): a file tree of the workspace + a viewer that re-renders when a
     file changes, so the user *sees* `PLAN.md` and docs update live. This mirrors the
     chat/canvas split of the original product.
   - Slash commands: `/ultraplan`, `/canvas`, `/new` (new workspace), `/help`, `/quit`.
   - Must feel polished: keybindings, scrolling, a footer with status + credit/session info.

5. **Ultraplan** (`agents/ultraplan.py`): the planning agent.
   - Invoked as an **isolated** call with **no chat history** — it receives only
     `canvas.snapshot()` plus a short "why now" context string. This amnesia is intentional:
     it must assess the project honestly without anchoring to the recent conversation.
   - Core idea: at any moment **one constraint** limits progress most; find it and plan only
     the **current phase** in detail (objective, sequential tasks with checkboxes, completion
     criteria, risks). Sketch future phases in a sentence or two only.
   - Writes the result to `PLAN.md`. The chat cofounder then walks the user through it and
     adjusts before treating it as committed.
   - Triggers: end of first-run context gathering; phase completion; user runs `/ultraplan`.

6. **First-run flow**: on a fresh workspace, the cofounder runs a short context-gathering
   conversation (what are you building, who's it for, what do you already know — one question
   at a time), captures answers into `docs/`, then calls Ultraplan to create the first plan.

---

## v1 scope (do this)

- Engine with subscription auth + session continuity.
- File-based canvas + live canvas pane.
- Cofounder chat that leads and persists decisions to the canvas.
- Ultraplan (isolated, canvas-only) writing `PLAN.md`.
- First-run context-gathering flow.
- `cofound` entry point, `--help`, and a README with setup + the `claude login` prerequisite.

## Out of scope for v1 (direction only — do NOT build yet)

Research (parallel multi-agent + citations), Brainstorming (community problem mining),
Website builder, Content calendar, Export bundles, real-time multi-user collaboration.
Leave clean seams so these slot in later (especially Research, which will spawn multiple
isolated engine calls in parallel and must be gated behind explicit user approval for cost).

---

## Conventions

- Type hints everywhere; `pydantic` models for canvas items and state.
- No model call outside `engine/`. No secrets in the repo.
- Prefer many small markdown files over one giant file on the canvas.
- Fail loud on auth/credit errors with a clear, actionable message.
- Write tests for the canvas layer and prompt-assembly logic (these don't need the model).
  Mock the engine in tests; never burn credits in the test suite.
- Keep the README's "Prerequisites" honest: user must have Claude Code installed and be
  logged in to a Pro/Max (or Team/Enterprise) plan; behavior and credits depend on the
  Agent SDK terms linked above.
- Naming: the project/command is **Cofound** (`cofound`); the AI persona is referred to as
  "your cofounder." Keep "Claude" out of the package name — describe it as "built on Claude"
  in docs instead.