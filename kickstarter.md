Read CLAUDE.md fully before doing anything. It is the source of truth for this project —
follow its constraints exactly, especially the auth and credit rules.

We're building v1 of "Cofound": a polished Python + Textual terminal app where a user works
with an AI cofounder that leads the conversation, plans strategically, and writes everything
to a file-based canvas. The CLI command and package are both `cofound`. v1 scope and build
order are defined in CLAUDE.md.

Here is the exact folder structure to scaffold. Follow it precisely.

REPO STRUCTURE (what we commit):

cofound/
├── pyproject.toml            # uv/pip config, cofound entry point
├── README.md
├── CLAUDE.md
├── src/
│   └── cofound/
│       ├── __init__.py
│       ├── __main__.py       # entry: `cofound` CLI
│       ├── cli.py            # arg parsing, --help, workspace init
│       ├── engine/           # the ONE place that touches the SDK
│       │   ├── __init__.py
│       │   ├── client.py     # ask(), stream, session resume, auth check
│       │   └── errors.py     # AuthMissing, CreditExhausted, etc.
│       ├── canvas/           # typed read/write over workspace files
│       │   ├── __init__.py
│       │   ├── workspace.py  # create/open workspace, snapshot()
│       │   ├── documents.py  # CRUD for docs/*.md
│       │   ├── notes.py      # CRUD for notes/*.md
│       │   ├── plan.py       # read/write/checkbox PLAN.md
│       │   └── state.py      # .cofound/state.json + config.json
│       ├── agents/           # isolated agent invocations
│       │   ├── __init__.py
│       │   └── ultraplan.py  # fresh call, canvas-only, writes PLAN.md
│       ├── prompts/          # version-controlled system prompts
│       │   ├── cofounder.md  # the leading/challenging persona
│       │   └── ultraplan.md  # constraint-focused planning prompt
│       └── ui/               # the Textual TUI
│           ├── __init__.py
│           ├── app.py        # main Textual App, layout, keybindings
│           ├── chat_pane.py  # conversation view, streaming, input
│           ├── canvas_pane.py# file tree + live doc viewer
│           ├── status_bar.py # footer: session, credits, phase
│           └── styles.css    # Textual CSS
└── tests/
    ├── __init__.py
    ├── test_canvas.py        # workspace/docs/notes/plan CRUD
    ├── test_state.py         # state + config serialization
    └── conftest.py           # engine mock fixtures

USER WORKSPACE (created per-project by `cofound --new`, never in the repo):

my-startup/
├── PLAN.md                   # Ultraplan writes this
├── docs/                     # cofounder persists decisions here
│   └── (created as you work)
├── notes/                    # short standalone notes
│   └── (created as you work)
└── .cofound/
    ├── config.json           # workspace settings (name, created_at)
    ├── state.json            # session id, current phase, last-plan ts
    └── log/                  # session transcripts / debug

Work in this order, and pause for my approval at each checkpoint:

STEP 0 — Verify before coding.
- Look up the CURRENT official Claude Agent SDK for Python docs and confirm the exact package
  name, import, and the precise way to make a call that authenticates with my existing Claude
  *subscription login* (the OAuth credential from running `claude`), NOT an API key, and NOT
  using --bare. Summarize what you found and the call you'll use. Do not guess from memory.
- Confirm the repo structure above matches CLAUDE.md and propose the full dependency list.
  Wait for my OK.

STEP 1 — Skeleton + engine.
- Scaffold the project with `uv` and a `cofound` console entry point.
- Implement the engine module as the single chokepoint for all model calls: a streaming
  `ask(...)` that uses subscription auth, returns/maintains a session id for multi-turn
  continuity, surfaces usage info when available, and fails with a clear message if I'm not
  logged in or out of credit.
- Give me a tiny throwaway script to confirm the engine talks to my subscription with ONE
  cheap call before we build more. Don't spend credits beyond that until I say go.

STEP 2 — Canvas layer.
- Implement typed read/write over the workspace layout in CLAUDE.md (docs/, notes/, PLAN.md,
  .cofound/state.json + config.json), plus a `snapshot()` that returns all canvas text.
- Unit-test this layer with the engine mocked. No real model calls in tests.

STEP 3 — System prompts.
- Write prompts/cofounder.md and prompts/ultraplan.md per CLAUDE.md. Show them to me to tune
  the persona before wiring them in.

STEP 4 — TUI.
- Build the Textual app: chat pane (streaming, with status indicators) + canvas pane (file
  tree + viewer that re-renders when files change). Slash commands /ultraplan /canvas /new
  /help /quit. A footer showing session + any available usage info. Make it feel polished.

STEP 5 — Ultraplan + first-run flow.
- Implement Ultraplan as an ISOLATED call with NO chat history — it gets only the canvas
  snapshot plus a short "why now" string — that writes PLAN.md (one constraint, current phase
  with checkbox tasks, brief future sketches).
- Implement the first-run context-gathering flow that then calls Ultraplan for the first plan.

STEP 6 — Wrap up.
- Write a README with prerequisites (Claude Code installed + logged in to a Pro/Max plan),
  setup, run instructions, and the credit caveat. Add a short "extending it" note pointing at
  the out-of-scope features (Research, etc.) and where they'd plug in. Describe Cofound as
  "built on Claude" rather than putting Claude in the package name.

Throughout: respect every constraint in CLAUDE.md. Keep model calls minimal, never call the
model in tests, ask before anything that would spend meaningful credit, and keep the engine
the only thing that touches the SDK. Get a minimal end-to-end loop working before polishing.

Start with STEP 0.