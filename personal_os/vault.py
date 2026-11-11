"""Vault discovery, configuration and Markdown primitives shared by every command."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REGISTRY_REL = "00-meta/block-registry.json"
IGNORED_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".venv", "__pycache__"}

DEFAULTS: dict = {
    "generated_snapshot": "00-meta/generated/block-state.md",
    "root_dashboard": "Home.md",
    "current_context": "00-meta/current-context.md",
    "session_dir": "00-meta/sessions",
    "decision_dir": "00-meta/decisions",
    "failure_modes": "00-meta/agent-failure-modes.md",
    "orientation": [
        "CLAUDE.md",
        "00-meta/current-context.md",
        "00-meta/generated/block-state.md",
        "00-meta/block-sync.md",
        "00-meta/agent-soul.md",
    ],
    "orientation_session_tail_lines": 50,
    "budget": {"target_tokens": 20000, "max_tokens": 25000},
    "doctor": {
        "stale_owner_days": 30,
        "current_context_days": 14,
        "folder_density_trigger": 30,
        "orphan_exempt": ["00-meta/sessions/", "00-meta/generated/", "00-meta/templates/", "90-archive/", "README.md"],
    },
}


class VaultError(Exception):
    """Raised for unrecoverable configuration problems."""


@dataclass
class Vault:
    root: Path
    registry: dict = field(default_factory=dict)

    @classmethod
    def discover(cls, start: Path | str | None = None) -> "Vault":
        """Walk up from `start` until a directory with a block registry is found."""
        here = Path(start or Path.cwd()).resolve()
        for candidate in (here, *here.parents):
            if (candidate / REGISTRY_REL).is_file():
                return cls.load(candidate)
        raise VaultError(f"no {REGISTRY_REL} found in {here} or any parent directory")

    @classmethod
    def load(cls, root: Path | str) -> "Vault":
        root = Path(root).resolve()
        path = root / REGISTRY_REL
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise VaultError(f"missing registry: {path}") from exc
        except json.JSONDecodeError as exc:
            raise VaultError(f"invalid JSON in {REGISTRY_REL}: {exc}") from exc
        return cls(root=root, registry=registry)

    def cfg(self, key: str):
        """Registry value with a documented default. Nested dicts merge one level deep."""
        default = DEFAULTS.get(key)
        value = self.registry.get(key, default)
        if isinstance(default, dict) and isinstance(value, dict):
            return {**default, **value}
        return value

    def path(self, rel: str) -> Path:
        return self.root / rel

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def markdown_files(self) -> list[Path]:
        return sorted(p for p in iter_files(self.root) if p.suffix == ".md")

    def all_files(self) -> list[Path]:
        return sorted(iter_files(self.root))


def iter_files(root: Path):
    for path in root.iterdir():
        if path.name in IGNORED_DIRS or (path.name.startswith(".") and path.is_dir()):
            continue
        if path.is_dir():
            yield from iter_files(path)
        elif path.is_file():
            yield path


_FM_LINE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$")


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """Return (frontmatter, body). Frontmatter is None when absent or unclosed.

    Only flat `key: value` pairs are parsed; that is all the system relies on.
    """
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = _FM_LINE.match(line)
        if match:
            data[match.group(1)] = match.group(2).strip("\"'")
    return data, text[end + 5 :]


def frontmatter(path: Path) -> dict[str, str]:
    data, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"missing or unclosed YAML frontmatter: {path.name}")
    return data
