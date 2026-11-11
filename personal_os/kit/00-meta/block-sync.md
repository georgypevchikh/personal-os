# Cross-Block Sync Contract

Prevents two failures: a block not knowing another block exists, and a consumer using a fact after its owner changed.

## Two layers
1. **Structural (automatic).** `block-registry.json` lists every block, its owner and dependencies. `pos check --write` derives `generated/block-state.md`; the pre-commit hook keeps it fresh.
2. **Semantic (assistant).** A script can see that a status changed, not what it *means*. After meaningful work, classify the event below and update every required consumer in the same work block.

## Propagation pass
1. Update the primary owner first.
2. Classify the event with the matrix.
3. Update required consumers; do not copy detail into unrelated blocks.
4. `pos check --write` (the hook prints reverse dependencies to review).
5. Session-log entry: `owner`, `event`, `propagated_to`, `not_applicable`.

## Event → consumer matrix
| Event | Primary owner | Required consumers |
|---|---|---|
| Project status / blocker / milestone changed | project `_home.md` | `current-context.md`; `30-projects/_home.md` if portfolio summary changes |
| New shipped capability or public evidence | project `_home.md` | `10-self/_home.md` if it is a stable capability; public profiles only after the claim is verified |
| Learning milestone | `20-learning/_home.md` | `current-context.md`; Self only once demonstrated |
| Block added / removed / renamed | new owner | `block-registry.json`; `Home.md`; `lookup-index.md`; decision log |
| Stable preference about the person | `10-self/calibration.md` | `agent-soul.md` only after recurrence |

## Non-propagation rules
- Shipping project work does not imply learning progress.
- A draft is not a published outcome.
- A lead is not a project.
