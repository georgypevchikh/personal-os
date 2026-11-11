"""Deterministic health check.

The original monthly health check was a checklist an LLM agent walked through.
Everything on it that can be decided mechanically lives here, so the agent's
review time goes to the judgment calls (is this open loop still real? is this
public claim still true?) instead of counting files.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date

from . import budget as budget_mod
from . import graph, links
from .vault import Vault, split_frontmatter

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


@dataclass
class Finding:
    severity: str  # error | warn | info
    check: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def _days_since(value: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(value[:10])).days
    except ValueError:
        return None


def run(vault: Vault, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    cfg = vault.cfg("doctor")
    findings: list[Finding] = []

    # 1. Block graph integrity (same rules the pre-commit hook enforces).
    rows: list[graph.BlockRow] = []
    try:
        rows = graph.validate(vault)
    except graph.GraphError as exc:
        findings += [Finding("error", "block-graph", e) for e in exc.errors]

    # 2. Owner freshness: active owners that nobody touched for too long.
    for row in rows:
        age = _days_since(row.updated, today)
        if row.status in {"active", "live"} and age is not None and age > cfg["stale_owner_days"]:
            findings.append(Finding("warn", "stale-owner", f"{row.id}: `{row.status}` but owner untouched for {age} days"))

    # 3. Current context is the cold-start anchor; stale anchor = stale agent.
    context = vault.path(vault.cfg("current_context"))
    if context.is_file():
        fm, _ = split_frontmatter(context.read_text(encoding="utf-8"))
        age = _days_since((fm or {}).get("updated", ""), today)
        if age is None:
            findings.append(Finding("warn", "current-context", "current context has no parseable `updated:` date"))
        elif age > cfg["current_context_days"]:
            findings.append(Finding("warn", "current-context", f"current context last updated {age} days ago"))
    else:
        findings.append(Finding("error", "current-context", f"missing {vault.cfg('current_context')}"))

    # 4. Snapshot drift: generated read model must match the owners.
    if rows and not graph.snapshot_is_fresh(vault, graph.render(vault, rows)):
        findings.append(Finding("warn", "snapshot", "generated block state is stale; run `pos check --write`"))

    # 5. Link graph.
    lg = links.build(vault)
    for note, target in lg.broken:
        findings.append(Finding("warn", "broken-link", f"{note} -> [[{target}]]"))
    for note in lg.orphans(cfg["orphan_exempt"]):
        findings.append(Finding("info", "orphan", f"{note} has no inbound links"))

    # 6. Density trigger: a folder that outgrows ~30 notes needs an index or a split.
    per_folder = Counter(vault.rel(p.parent) for p in vault.markdown_files())
    for folder, count in sorted(per_folder.items()):
        if count > cfg["folder_density_trigger"]:
            findings.append(Finding("info", "density", f"{folder}/ holds {count} notes (> {cfg['folder_density_trigger']})"))

    # 7. Orientation budget.
    report = budget_mod.measure(vault, today)
    if report.status == "over":
        findings.append(Finding("error", "budget", f"session orientation ~{report.total} tokens > max {report.maximum}"))
    elif report.status == "above-target":
        findings.append(Finding("warn", "budget", f"session orientation ~{report.total} tokens > target {report.target}"))
    for item in report.items:
        if not item.present:
            findings.append(Finding("warn", "budget", f"orientation file missing: {item.source}"))

    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.check, f.message))
