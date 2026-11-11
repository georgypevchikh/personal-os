"""Orientation budget: what does it cost an agent to start a session in this vault?

A rule like "keep session orientation under ~25K tokens" is useless if nobody
measures it. This module measures it on every run and can fail CI when the
budget is exceeded.

Token counts are a local *estimate* (no network call, no content leaves the
machine): ~4 characters per token for ASCII text and ~2.5 for other scripts
(e.g. Cyrillic), which tokenizes less efficiently. Treat the result as an
order-of-magnitude guard, not a bill.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .vault import Vault


def estimate_tokens(text: str) -> int:
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    other = len(text) - ascii_chars
    return round(ascii_chars / 4 + other / 2.5)


@dataclass
class BudgetItem:
    source: str
    tokens: int
    present: bool


@dataclass
class BudgetReport:
    items: list[BudgetItem]
    target: int
    maximum: int

    @property
    def total(self) -> int:
        return sum(i.tokens for i in self.items)

    @property
    def status(self) -> str:
        if self.total > self.maximum:
            return "over"
        if self.total > self.target:
            return "above-target"
        return "ok"


def measure(vault: Vault, today: date | None = None) -> BudgetReport:
    items: list[BudgetItem] = []
    for rel in vault.cfg("orientation"):
        path = vault.path(rel)
        if path.is_file():
            items.append(BudgetItem(rel, estimate_tokens(path.read_text(encoding="utf-8")), True))
        else:
            items.append(BudgetItem(rel, 0, False))
    tail = int(vault.cfg("orientation_session_tail_lines"))
    day = (today or date.today()).isoformat()
    log = vault.path(f"{vault.cfg('session_dir')}/{day}.md")
    if tail and log.is_file():
        lines = log.read_text(encoding="utf-8").splitlines()[-tail:]
        items.append(BudgetItem(f"session log tail ({tail} lines)", estimate_tokens("\n".join(lines)), True))
    limits = vault.cfg("budget")
    return BudgetReport(items, int(limits["target_tokens"]), int(limits["max_tokens"]))
