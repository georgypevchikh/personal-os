# System Rules

## Structure
- `00-meta/` system: context, rules, decisions, sessions, generated state.
- `NN-domain/_home.md` one owner per domain. Projects are folder-hubs: `30-projects/<name>/_home.md`.
- `90-archive/` finished or abandoned material, with a successor link.
- `private/` git-ignored. Anything sensitive.

## Ownership
Every fact has one owner file. Other files link to it, never copy it. Owners carry frontmatter: `title`, `status`, `updated`, `sync_registry`.

## Memory streams → long memory
- **Session logs** (`00-meta/sessions/YYYY-MM-DD.md`): dense entries — decisions, status, next step, open loops. Written by the assistant every 5–10 substantive exchanges.
- **Decision logs** (`00-meta/decisions/YYYY-MM-DD-slug.md`): context → decision → reasoning → trade-offs → review-later.
- **Weekly review**: consolidate session logs into owners; promote stable observations; prune open loops.

## Change policy
- Plans change at the weekly review, not mid-week. Ideas during the week go to notes.
- Architecture changes need a decision log.

## Budget
Cold start should cost 10–20K tokens; above ~25K compact history before removing graph awareness. `pos budget` measures it.
