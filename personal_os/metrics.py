"""Aggregate-only vault metrics.

Privacy contract (enforced by tests): the output contains numbers, ISO dates,
week/month buckets and top-level area names matching `NN-name` — never a note
title, file name, path below the top level, block id, or a single word of
content. It is safe to publish the JSON of a private vault.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import date, timedelta

from . import budget, links
from .vault import Vault, split_frontmatter

AREA = re.compile(r"^\d{2}-[a-z0-9-]+$")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})")
FAILURE_MODE = re.compile(r"(?m)^##\s+FM-\d+")
WORD = re.compile(r"\w+", re.UNICODE)


def _area(rel: str) -> str:
    top = rel.split("/", 1)[0] if "/" in rel else "(root)"
    return top if top == "(root)" or AREA.match(top) else "(other)"


def _iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _dated_files(vault: Vault, rel_dir: str) -> list[date]:
    folder = vault.path(rel_dir)
    days = []
    if folder.is_dir():
        for p in folder.glob("*.md"):
            m = DATED.match(p.name)
            if m:
                try:
                    days.append(date.fromisoformat(m.group(1)))
                except ValueError:
                    pass
    return sorted(days)


def _git_days(vault: Vault) -> list[date]:
    try:
        out = subprocess.run(
            ["git", "-C", str(vault.root), "log", "--format=%cs"], check=True, capture_output=True, text=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(date.fromisoformat(line) for line in out.split() if line)


def _gaps(days: list[date]) -> int:
    unique = sorted(set(days))
    return max(((b - a).days for a, b in zip(unique, unique[1:])), default=0)


def _weekly_series(days: list[date]) -> dict[str, int]:
    """Continuous weekly series (zero-filled) so charts show pauses honestly."""
    if not days:
        return {}
    counts = Counter(_iso_week(d) for d in days)
    start = days[0] - timedelta(days=days[0].weekday())
    series: dict[str, int] = {}
    cursor = start
    while cursor <= days[-1]:
        key = _iso_week(cursor)
        series[key] = counts.get(key, 0)
        cursor += timedelta(days=7)
    return series


PREFIX = {"system": "S", "domain": "D", "project": "P"}


def anonymous_graph(vault: Vault) -> dict:
    """The block graph with every id replaced by kind + index (S1, D1, P1 …).

    Shape and status survive (enough to draw the system), names do not.
    """
    blocks = vault.registry.get("blocks", [])
    counters: Counter = Counter()
    alias: dict[str, str] = {}
    nodes = []
    for block in blocks:
        prefix = PREFIX.get(block.get("kind", ""), "X")
        counters[prefix] += 1
        alias[block.get("id")] = f"{prefix}{counters[prefix]}"
        owner = vault.path(block.get("owner", ""))
        fm, _ = split_frontmatter(owner.read_text(encoding="utf-8")) if owner.is_file() else (None, "")
        nodes.append({"id": alias[block.get("id")], "kind": block.get("kind", "unknown"), "status": (fm or {}).get("status", "missing")})
    edges = [
        [alias[b.get("id")], alias[dep]]
        for b in blocks
        for dep in b.get("depends_on", [])
        if dep in alias
    ]
    return {"nodes": nodes, "edges": edges}


def collect(vault: Vault, today: date | None = None) -> dict:
    today = today or date.today()
    notes = vault.markdown_files()
    rels = [vault.rel(p) for p in notes]
    words = sum(len(WORD.findall(p.read_text(encoding="utf-8", errors="replace"))) for p in notes)

    lg = links.build(vault)
    linked = sum(1 for targets in lg.outgoing.values() if targets)
    orphans = lg.orphans(vault.cfg("doctor")["orphan_exempt"])

    blocks = vault.registry.get("blocks", [])
    statuses: Counter = Counter()
    for block in blocks:
        owner = vault.path(block.get("owner", ""))
        status = "missing"
        if owner.is_file():
            fm, _ = split_frontmatter(owner.read_text(encoding="utf-8"))
            status = (fm or {}).get("status", "missing")
        statuses[status] += 1

    fm_file = vault.path(vault.cfg("failure_modes"))
    failure_modes = len(FAILURE_MODE.findall(fm_file.read_text(encoding="utf-8"))) if fm_file.is_file() else 0
    sessions = _dated_files(vault, vault.cfg("session_dir"))
    decisions = _dated_files(vault, vault.cfg("decision_dir"))
    commits = _git_days(vault)
    report = budget.measure(vault, today)

    return {
        "schema": 1,
        "generated_on": today.isoformat(),
        "notes": {
            "total": len(notes),
            "words": words,
            "by_area": dict(sorted(Counter(_area(r) for r in rels).items())),
        },
        "links": {
            "total": lg.total_links,
            "broken": len(lg.broken),
            "orphans": len(orphans),
            "notes_with_outgoing_pct": round(100 * linked / len(notes), 1) if notes else 0.0,
            "avg_outgoing": round(lg.total_links / len(notes), 2) if notes else 0.0,
        },
        "blocks": {
            "total": len(blocks),
            "dependency_edges": sum(len(b.get("depends_on", [])) for b in blocks),
            "by_kind": dict(sorted(Counter(b.get("kind", "unknown") for b in blocks).items())),
            "by_status": dict(sorted(statuses.items())),
            "graph": anonymous_graph(vault),
        },
        "memory": {
            "session_logs": len(sessions),
            "decision_logs": len(decisions),
            "failure_modes": failure_modes,
            "decisions_by_month": dict(sorted(Counter(d.strftime("%Y-%m") for d in decisions).items())),
        },
        "git": {
            "commits": len(commits),
            "first": commits[0].isoformat() if commits else None,
            "last": commits[-1].isoformat() if commits else None,
            "active_days": len(set(commits)),
            "longest_gap_days": _gaps(commits),
            "weekly": _weekly_series(commits),
        },
        "orientation": {"tokens_estimate": report.total, "target": report.target, "max": report.maximum},
    }
