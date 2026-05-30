# Cofound

> An AI cofounder in your terminal. It leads the conversation, plans strategically,
> and writes everything to a local file-based canvas. Built on Claude.

Runs on **your own Claude subscription login** — no API key required.

> ⚠️ Work in progress. This README is a placeholder; the full setup guide,
> prerequisites, and credit notes are written in STEP 6.

## Prerequisites (short version)

1. Install **Claude Code** and run `claude` once to log in to your Pro/Max
   (or Team/Enterprise) plan.
2. Install [`uv`](https://docs.astral.sh/uv/).

## Quick start

```bash
uv sync
uv run python smoke_test.py   # one cheap call to confirm auth + streaming
cofound doctor                # no-cost environment check
```
