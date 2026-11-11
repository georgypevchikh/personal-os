# AGENTS.md — entry point for Codex, Cursor and other runtimes

Semantic mirror of `CLAUDE.md` — edit both together.

## Cold start
No hook runs here. Read, in order: `00-meta/current-context.md` → `00-meta/generated/block-state.md` → `00-meta/block-sync.md` → today's session log tail → `00-meta/agent-soul.md`.

## On demand
`00-meta/lookup-index.md` (where things live) · `00-meta/system-rules.md` (protocols) · `00-meta/agent-failure-modes.md` (your known mistakes) · `<domain>/_home.md`.

## Hard rules
1. One owner per status; never create a parallel source of truth.
2. Autosave a dense entry to `00-meta/sessions/YYYY-MM-DD.md` every 5–10 substantive exchanges.
3. After meaningful work, run the propagation pass in `00-meta/block-sync.md`.
4. Never say "done" before running the check that proves it.
5. No secrets in the vault. Private material lives in `private/` (git-ignored).
