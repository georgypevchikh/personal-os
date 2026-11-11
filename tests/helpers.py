"""Test fixtures: build small throwaway vaults on disk."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from personal_os.init import scaffold
from personal_os.vault import Vault

GIT_ENV = ["-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def owner_note(title: str, status: str = "active", updated: str = "2026-01-01", body: str = "") -> str:
    return (
        f"---\ntitle: {title}\ntype: domain-home\nstatus: {status}\n"
        f"sync_registry: 00-meta/block-registry.json\nupdated: {updated}\n---\n\n# {title}\n{body}\n"
    )


class VaultCase(unittest.TestCase):
    """Each test gets a fresh temporary directory, removed afterwards."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pos-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def minimal_vault(self, blocks: list[dict] | None = None, **registry) -> Vault:
        blocks = blocks or [
            {"id": "meta", "kind": "system", "owner": "00-meta/current-context.md", "depends_on": ["self"]},
            {"id": "self", "kind": "domain", "owner": "10-self/_home.md", "depends_on": []},
        ]
        self.write("00-meta/block-registry.json", json.dumps({"version": 1, "blocks": blocks, **registry}))
        self.write("00-meta/current-context.md", owner_note("Current Context", updated="2026-01-01"))
        self.write("10-self/_home.md", owner_note("Self"))
        self.write("Home.md", "# Home\n[[10-self/_home|Self]]\n")
        return Vault.load(self.tmp)

    def kit_vault(self, git: bool = True) -> Vault:
        scaffold(self.tmp / "vault", owner="Test Owner", git=git)
        return Vault.load(self.tmp / "vault")

    def git(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *GIT_ENV, *args], capture_output=True, text=True)
