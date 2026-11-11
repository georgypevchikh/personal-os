"""`pos init`: scaffold a working vault from the bundled starter kit."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from importlib import resources
from pathlib import Path

from . import graph
from .vault import Vault

TEXT_SUFFIXES = {".md", ".json", ".sh", ""}


def _kit_root() -> Path:
    return Path(str(resources.files("personal_os") / "kit"))


def scaffold(target: Path, owner: str, git: bool = True, force: bool = False) -> list[str]:
    """Copy the kit into `target`, fill placeholders, optionally init git + hooks.

    Files named `dot-*` become `.*` (hidden files survive packaging this way).
    Returns the list of created relative paths.
    """
    target = target.expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"{target} is not empty (use --force to scaffold into it anyway)")
    target.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    created: list[str] = []
    kit = _kit_root()
    for src in sorted(kit.rglob("*")):
        if src.is_dir() or src.name == ".gitkeep-src" or "__pycache__" in src.parts:
            continue
        rel_parts = [p.replace("dot-", ".", 1) if p.startswith("dot-") else p for p in src.relative_to(kit).parts]
        dest = target.joinpath(*rel_parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in TEXT_SUFFIXES:
            text = src.read_text(encoding="utf-8").replace("{{OWNER}}", owner).replace("{{TODAY}}", today)
            dest.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dest)
        if dest.parent.name == ".githooks":
            dest.chmod(0o755)
        created.append(dest.relative_to(target).as_posix())

    if git and not (target / ".git").exists():
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)
    if git:
        subprocess.run(["git", "-C", str(target), "config", "core.hooksPath", ".githooks"], check=True)
    vault = Vault.load(target)
    graph.write_snapshot(vault, graph.render(vault, graph.validate(vault)))
    created.append(vault.cfg("generated_snapshot"))
    return created
