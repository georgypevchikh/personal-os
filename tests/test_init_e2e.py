"""End to end: scaffold a vault, commit through the real hook, prove the guards fire."""

import os
import shutil
import unittest
from pathlib import Path

from personal_os.cli import main
from personal_os.vault import frontmatter

from tests.helpers import VaultCase

HAS_POS = shutil.which("pos") is not None


class InitTests(VaultCase):
    def test_scaffold_creates_hidden_files_and_valid_graph(self):
        vault = self.kit_vault(git=False)
        for rel in (".claude/settings.json", ".githooks/pre-commit", ".gitignore", "CLAUDE.md", "AGENTS.md"):
            self.assertTrue(vault.path(rel).is_file(), rel)
        self.assertTrue(os.access(vault.path(".githooks/pre-commit"), os.X_OK))
        self.assertNotIn("{{", vault.path("10-self/_home.md").read_text())
        self.assertEqual(main(["check", "--vault", str(vault.root), "--write", "--check"]), 0)

    def test_refuses_non_empty_target(self):
        (self.tmp / "vault").mkdir()
        (self.tmp / "vault" / "existing.md").write_text("x")
        self.assertEqual(main(["init", str(self.tmp / "vault")]), 1)


@unittest.skipUnless(HAS_POS, "needs `pos` on PATH (pip install -e .)")
class HookTests(VaultCase):
    def commit(self, root: Path, message: str):
        self.git(root, "add", "-A")
        return self.git(root, "commit", "-q", "-m", message)

    def test_hook_allows_clean_commit_and_stamps_owner(self):
        vault = self.kit_vault()
        self.assertEqual(self.commit(vault.root, "init").returncode, 0)
        owner = vault.path("10-self/_home.md")
        owner.write_text(owner.read_text().replace("updated: ", "updated: 2000-01-01 #"), encoding="utf-8")
        text = owner.read_text().replace("updated: 2000-01-01 #", "updated: 2000-01-01\nold: ")
        owner.write_text(text, encoding="utf-8")
        result = self.commit(vault.root, "edit self")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(frontmatter(owner)["updated"], "2000-01-01", "hook must auto-stamp freshness")

    def test_hook_blocks_secrets_and_private_paths(self):
        vault = self.kit_vault()
        self.commit(vault.root, "init")
        vault.path("30-projects/leak.md").write_text("ghp_" + "Z" * 36, encoding="utf-8")
        self.assertNotEqual(self.commit(vault.root, "leak").returncode, 0)
        self.git(vault.root, "reset", "-q")
        vault.path("30-projects/leak.md").unlink()
        vault.path(".env").write_text("X=1", encoding="utf-8")
        self.git(vault.root, "add", "-f", ".env")
        self.assertNotEqual(self.git(vault.root, "commit", "-q", "-m", "env").returncode, 0)

    def test_hook_blocks_broken_graph(self):
        vault = self.kit_vault()
        self.commit(vault.root, "init")
        vault.path("Home.md").write_text("# dashboard lost its links\n", encoding="utf-8")
        result = self.commit(vault.root, "break graph")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not linked from Home.md", result.stderr)
