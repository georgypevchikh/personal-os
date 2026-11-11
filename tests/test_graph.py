import json
from datetime import date

from personal_os import graph
from personal_os.vault import Vault, frontmatter

from tests.helpers import VaultCase, owner_note


class ValidateTests(VaultCase):
    def test_minimal_vault_is_valid(self):
        rows = graph.validate(self.minimal_vault())
        self.assertEqual([r.id for r in rows], ["meta", "self"])

    def test_unknown_dependency_is_reported(self):
        vault = self.minimal_vault(
            blocks=[{"id": "self", "kind": "domain", "owner": "10-self/_home.md", "depends_on": ["ghost"]}]
        )
        with self.assertRaises(graph.GraphError) as ctx:
            graph.validate(vault)
        self.assertIn("unknown dependencies: ghost", str(ctx.exception))

    def test_duplicate_ids_and_self_dependency(self):
        block = {"id": "self", "kind": "domain", "owner": "10-self/_home.md", "depends_on": ["self"]}
        with self.assertRaises(graph.GraphError) as ctx:
            graph.validate(self.minimal_vault(blocks=[block, dict(block)]))
        message = str(ctx.exception)
        self.assertIn("duplicate block id", message)
        self.assertIn("depends on itself", message)

    def test_missing_frontmatter_and_registry_pointer(self):
        vault = self.minimal_vault()
        self.write("10-self/_home.md", "# no frontmatter\n")
        with self.assertRaises(graph.GraphError) as ctx:
            graph.validate(vault)
        self.assertIn("frontmatter", str(ctx.exception))

    def test_domain_must_be_linked_from_dashboard(self):
        vault = self.minimal_vault()
        self.write("Home.md", "# Home without links\n")
        with self.assertRaises(graph.GraphError) as ctx:
            graph.validate(vault)
        self.assertIn("not linked from Home.md", str(ctx.exception))

    def test_live_project_must_appear_in_current_context(self):
        blocks = [{"id": "app", "kind": "project", "owner": "30-projects/app/_home.md", "depends_on": []}]
        vault = self.minimal_vault(blocks=blocks)
        self.write("30-projects/app/_home.md", owner_note("App", status="live"))
        with self.assertRaises(graph.GraphError) as ctx:
            graph.validate(vault)
        self.assertIn("absent from 00-meta/current-context.md", str(ctx.exception))
        self.write("00-meta/current-context.md", owner_note("Current Context", body="- app: shipping"))
        self.assertEqual(len(graph.validate(vault)), 1)


class SnapshotTests(VaultCase):
    def test_write_then_fresh(self):
        vault = self.minimal_vault()
        output = graph.render(vault, graph.validate(vault))
        self.assertFalse(graph.snapshot_is_fresh(vault, output))
        self.assertTrue(graph.write_snapshot(vault, output))
        self.assertTrue(graph.snapshot_is_fresh(vault, output))
        self.assertFalse(graph.write_snapshot(vault, output), "second write must be a no-op")

    def test_render_lists_every_block(self):
        vault = self.minimal_vault()
        output = graph.render(vault, graph.validate(vault))
        self.assertIn("| `meta` |", output)
        self.assertIn("| `self` |", output)


class StampTests(VaultCase):
    def test_stamps_only_changed_stale_owners(self):
        vault = self.minimal_vault()
        today = date(2026, 3, 4).isoformat()
        stamped = graph.stamp_changed_owners(vault, {"10-self/_home.md"}, today)
        self.assertEqual(stamped, ["10-self/_home.md"])
        self.assertEqual(frontmatter(vault.path("10-self/_home.md"))["updated"], today)
        self.assertEqual(frontmatter(vault.path("00-meta/current-context.md"))["updated"], "2026-01-01")
        self.assertEqual(graph.stamp_changed_owners(vault, {"10-self/_home.md"}, today), [])

    def test_reverse_dependencies(self):
        vault = self.minimal_vault()
        self.assertEqual(graph.reverse_dependencies(vault, {"10-self/_home.md"}), ["meta"])
        self.assertEqual(graph.reverse_dependencies(vault, {"unrelated.md"}), [])


class DiscoveryTests(VaultCase):
    def test_discover_walks_up(self):
        self.minimal_vault()
        nested = self.tmp / "10-self"
        self.assertEqual(Vault.discover(nested).root, self.tmp.resolve())

    def test_config_defaults_merge(self):
        vault = self.minimal_vault(budget={"max_tokens": 9})
        self.assertEqual(vault.cfg("budget"), {"target_tokens": 20000, "max_tokens": 9})
        self.assertEqual(json.loads((self.tmp / "00-meta/block-registry.json").read_text())["version"], 1)
