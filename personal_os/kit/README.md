# {{OWNER}} — Personal OS

A local-first memory layer for working with AI agents. Plain Markdown + git; any agent (Claude Code, Codex, Cursor) can read it.

## First 10 minutes

1. Open this folder in Obsidian (optional — it is just Markdown).
2. Fill in `10-self/_home.md` (who you are) and `00-meta/current-context.md` (what is true right now).
3. Start your agent **inside this folder**. In Claude Code the SessionStart hook injects current state automatically; other runtimes read `AGENTS.md`.
4. Work. The agent appends a dense entry to `00-meta/sessions/YYYY-MM-DD.md` every few meaningful exchanges.
5. Commit. The pre-commit hook stamps freshness, regenerates the block graph and blocks secrets.

## Commands

```bash
pos check --write   # validate the block graph, refresh 00-meta/generated/block-state.md
pos doctor          # deterministic health check (links, freshness, density, budget)
pos budget          # token cost of a cold start
pos metrics         # aggregate-only numbers, safe to share
```

## Rules that keep it working

- **One owner per fact.** Every status lives in exactly one file; others link to it.
- **Rules become mechanisms.** If a rule is broken twice, automate it or delete it.
- **Assistant mistakes are data.** Log them in `00-meta/agent-failure-modes.md` with a prevention rule.
- **Anything private goes to `private/`** (git-ignored) or a password manager — never into notes.
