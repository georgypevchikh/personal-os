# Roadmap

Ordered by what unblocks the most, not by what is most fun to build. Each item states the trigger that justifies it — the same rule the system applies to itself.

## Now: dogfood

1. **Run `pos` on the private vault in place of the original scripts.** First `pos doctor` findings (three stale domains, 38 broken links) become the first cleanup.
2. **Doctor in CI on the private vault** as a weekly job, so the audit runs without anyone remembering it.
3. **Three external users.** The kit has been tested by one person. Success metric: time from `pos init` to a first session where the agent correctly answers "what am I working on?" without being told. Target: under 15 minutes.

## Next: an AI layer with a hard $5/month ceiling

The deterministic core stops exactly where meaning starts (see [case study 3](case-studies.md#3-one-part-of-the-system-didnt-know-another-part-had-changed)). That boundary is where a model earns its cost. Only three jobs qualify:

| Job | When | Input → output | Why a model and not code |
|---|---|---|---|
| **Propagation reviewer** | pre-push, when an owner changed | changed owner diff + sync contract + summaries of dependent owners → list of consumers that need an update, with reasons | Deciding whether a milestone changes a public claim is semantic |
| **Weekly review draft** | once a week, Batch API | the week's session logs + current context → draft review in `inbox/` for the person to edit | Consolidating streams into long memory is summarisation and judgment |
| **Failure-mode candidates** | with the weekly review | session logs → proposed `FM-NNN` entries the assistant missed | Spotting a repeated mistake across days needs reading, not regex |

### Budget design

| Lever | Detail |
|---|---|
| Model | Claude Opus 5.5 by default at `low`/`medium` effort; a cheaper model only if an eval shows it holds quality on these three jobs |
| Price basis | $4 / $20 per million input / output tokens; cached prompt prefix and the Batch API (−50%) for the weekly job |
| Estimate | Propagation review ≈ 8K in / 0.8K out ≈ $0.05 × ~60 per month ≈ $2.90. Weekly draft ≈ 40K in / 4K out ≈ $0.24, batched ≈ $0.12 × 4.3 ≈ $0.52. **≈ $3.40 per month**, leaving headroom under the cap |
| Hard cap | A local usage ledger records the cost of every call from the API's own `usage` numbers. Before each call: month-to-date spend + estimated cost of this call > $5 → refuse, and fall back to the deterministic output. A provider-side workspace spend limit and a dedicated key are the second layer where available |
| Failure mode | Over budget or API down → the hook prints the reverse-dependency list it prints today. The model is an upgrade, never a dependency |

### Privacy design

- Only files on an explicit allowlist (the orientation set and changed owners) are sent; `private/` never leaves the machine.
- Every outgoing prompt passes through the same `pos scan` rules as a public commit — secrets, e-mails, home paths and the private denylist — before it is sent.
- Prompts and responses are logged locally for audit, never in the vault's git history.

## Later: make it usable for anyone

| Idea | Trigger to build it |
|---|---|
| **`pos mcp`** — a read-only MCP server exposing `get_context`, `get_block`, `search_owners`, `doctor` to any agent client | A second runtime family needs the vault without hooks |
| **Persona templates** for `pos init` (student, freelancer, team lead) | First external users ask for a different domain set |
| **Obsidian panel** showing doctor findings and the block graph | Users who never open a terminal |
| **Orientation eval** — scripted first questions ("what is blocked?", "what did we decide about X?") scored against current context | Any change to the orientation set or budget |
| **Semantic search** over owners and decisions | A folder crosses the density trigger (~30 notes) or lookup-index misses become frequent |
| **Session-log compaction** into monthly highlights | Orientation budget crosses the 20K target |

## Theoretical improvements worth testing

- **Propagation precision/recall.** Label a month of owner changes by hand and measure how often the reverse-dependency list over- and under-reports. This tells us whether the dependency edges are right, before any model is added.
- **Cost of a wrong cold start.** Compare sessions with and without injected context on the same scripted tasks: corrections needed, tokens spent, wrong-file edits. This turns "orientation is worth 10K tokens" from an argument into a number.
- **Rule half-life.** Track how long a prose rule survives before it is either automated or deleted. The hypothesis is that prose rules that are not mechanised within ~2 recurrences never hold.
