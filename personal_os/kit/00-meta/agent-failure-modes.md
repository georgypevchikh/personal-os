# Agent Failure Modes

The assistant's self-correction catalog. Every entry: what happened → root cause → trigger → prevention rule. Add one in the same session a mistake happens, whether or not the person noticed it.

## FM-001 — Cold-start skip on a casual opener
- **What happened:** a session opened with "hi"; the assistant answered without reading current context and gave stale advice.
- **Root cause:** treated a greeting as not needing orientation.
- **Trigger:** first message of a session, any content.
- **Prevention:** current context is in the prompt (hook) or read first — always.

## FM-002 — Reported a fix that was never run
- **What happened:** said "fixed" after editing code, without running the command that proves it.
- **Root cause:** confused intent with outcome.
- **Trigger:** about to write "done", "fixed", "works".
- **Prevention:** run the verification, read its output, then report — with the output.
