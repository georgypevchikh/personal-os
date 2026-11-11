# CLAUDE.md — entry point for Claude Code

Thin entry. Rules live in shared files so every runtime reads the same thing. `AGENTS.md` mirrors this file for other runtimes — edit both together.

## Cold start
The SessionStart hook injects `00-meta/current-context.md`, the generated block graph, the sync contract and today's session-log tail. **Then read `00-meta/agent-soul.md` before your first substantive answer.** If no injected block is visible, read `00-meta/current-context.md` yourself first.

## On demand
`00-meta/lookup-index.md` (where things live) · `00-meta/system-rules.md` (protocols) · `00-meta/agent-failure-modes.md` (your known mistakes) · `<domain>/_home.md`.

## Hard rules
1. One owner per status; never create a parallel source of truth.
2. Autosave a dense entry to `00-meta/sessions/YYYY-MM-DD.md` every 5–10 substantive exchanges.
3. After meaningful work, run the propagation pass in `00-meta/block-sync.md`.
4. Never say "done" before running the check that proves it.
5. No secrets in the vault. Private material lives in `private/` (git-ignored).
