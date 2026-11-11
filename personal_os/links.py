"""Wikilink graph: parse `[[links]]` the way Obsidian resolves them, find broken links and orphans."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .vault import Vault

WIKILINK = re.compile(r"!?\[\[([^\]\n]+?)\]\]")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")


@dataclass
class LinkGraph:
    notes: set[str]
    outgoing: dict[str, list[str]] = field(default_factory=dict)  # note -> resolved targets
    broken: list[tuple[str, str]] = field(default_factory=list)  # (note, raw target)
    total_links: int = 0

    @property
    def inbound(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = defaultdict(set)
        for source, targets in self.outgoing.items():
            for target in targets:
                if target != source:
                    result[target].add(source)
        return result

    def orphans(self, exempt: list[str]) -> list[str]:
        inbound = self.inbound
        return sorted(
            note
            for note in self.notes
            if "/" in note  # root-level files are entry points (dashboard, CLAUDE.md, AGENTS.md)
            and not inbound.get(note)
            and not any(note.startswith(p) or note.endswith(p) for p in exempt)
        )


def extract_links(text: str) -> list[str]:
    """Raw link targets, skipping fenced code blocks and inline code spans."""
    targets: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in WIKILINK.finditer(INLINE_CODE.sub("", line)):
            target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            target = target.rstrip("\\")  # `[[a\|b]]` inside Markdown tables
            if target:
                targets.append(target)
    return targets


def _normalise(path: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(path).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def build(vault: Vault) -> LinkGraph:
    files = [vault.rel(p) for p in vault.all_files()]
    notes = {f for f in files if f.endswith(".md")}
    lower_files = {f.lower(): f for f in files}
    by_name: dict[str, list[str]] = defaultdict(list)
    for f in files:
        name = PurePosixPath(f).name.lower()
        by_name[name].append(f)
        if name.endswith(".md"):
            by_name[name[:-3]].append(f)

    def resolve(source: str, target: str) -> str | None:
        candidates = [target] if PurePosixPath(target).suffix else [target + ".md", target]
        if "/" in target:
            base = str(PurePosixPath(source).parent)
            for cand in candidates:
                for path in (_normalise(f"{base}/{cand}"), _normalise(cand)):
                    if path.lower() in lower_files:
                        return lower_files[path.lower()]
            return None
        for cand in candidates:
            hits = by_name.get(cand.lower())
            if hits:
                return sorted(hits, key=len)[0]  # Obsidian prefers the shortest path
        return None

    graph = LinkGraph(notes=notes)
    for note in sorted(notes):
        text = vault.path(note).read_text(encoding="utf-8", errors="replace")
        resolved: list[str] = []
        for target in extract_links(text):
            graph.total_links += 1
            hit = resolve(note, target)
            if hit is None:
                graph.broken.append((note, target))
            else:
                resolved.append(hit)
        graph.outgoing[note] = resolved
    return graph
