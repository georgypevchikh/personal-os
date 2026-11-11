from datetime import date

from personal_os import budget, doctor, links

from tests.helpers import VaultCase, owner_note


class ExtractTests(VaultCase):
    def test_aliases_headings_embeds_and_code_are_handled(self):
        text = "\n".join(
            [
                "See [[note-a|Alias]] and [[folder/note-b#Heading]] and ![[image.png]].",
                "Inline `[[not-a-link]]` is ignored.",
                "```",
                "[[also-not-a-link]]",
                "```",
                "| table | [[note-c\\|Alias]] |",
            ]
        )
        self.assertEqual(links.extract_links(text), ["note-a", "folder/note-b", "image.png", "note-c"])


class GraphBuildTests(VaultCase):
    def test_resolution_broken_links_and_orphans(self):
        vault = self.minimal_vault()
        self.write("20-notes/a.md", "[[b]] [[../10-self/_home]] [[missing]]")
        self.write("20-notes/b.md", "[[a]] ![[pic.png]]")
        self.write("20-notes/pic.png", "binary")
        self.write("20-notes/lonely.md", "nobody links here")
        graph = links.build(vault)
        self.assertEqual(graph.broken, [("20-notes/a.md", "missing")])
        self.assertIn("10-self/_home.md", graph.outgoing["20-notes/a.md"])
        orphans = graph.orphans([])
        self.assertIn("20-notes/lonely.md", orphans)
        self.assertNotIn("20-notes/a.md", orphans)
        self.assertNotIn("Home.md", orphans, "root-level entry points are never orphans")


class DoctorTests(VaultCase):
    def test_fresh_kit_has_no_errors_or_warnings(self):
        vault = self.kit_vault(git=False)
        findings = doctor.run(vault)
        self.assertEqual([f for f in findings if f.severity != "info"], [])

    def test_detects_stale_owner_broken_link_and_stale_context(self):
        vault = self.minimal_vault()
        self.write("10-self/_home.md", owner_note("Self", updated="2026-01-01", body="[[nowhere]]"))
        findings = doctor.run(vault, today=date(2026, 6, 1))
        checks = {(f.severity, f.check) for f in findings}
        self.assertIn(("warn", "stale-owner"), checks)
        self.assertIn(("warn", "broken-link"), checks)
        self.assertIn(("warn", "current-context"), checks)

    def test_graph_errors_are_errors(self):
        vault = self.minimal_vault()
        self.write("Home.md", "# empty\n")
        self.assertTrue(any(f.severity == "error" and f.check == "block-graph" for f in doctor.run(vault)))

    def test_density_trigger(self):
        vault = self.minimal_vault(doctor={"folder_density_trigger": 2})
        for i in range(3):
            self.write(f"20-notes/n{i}.md", "x")
        self.assertTrue(any(f.check == "density" and "20-notes" in f.message for f in doctor.run(vault)))


class BudgetTests(VaultCase):
    def test_estimate_weights_non_ascii_heavier(self):
        self.assertEqual(budget.estimate_tokens("abcd" * 10), 10)
        self.assertEqual(budget.estimate_tokens("абвгд" * 10), 20)

    def test_over_budget_is_reported_and_missing_files_flagged(self):
        vault = self.minimal_vault(budget={"target_tokens": 1, "max_tokens": 2})
        report = budget.measure(vault)
        self.assertEqual(report.status, "over")
        self.assertTrue(any(not item.present for item in report.items))

    def test_session_log_tail_is_counted(self):
        vault = self.minimal_vault()
        self.write("00-meta/sessions/2026-02-03.md", "line\n" * 200)
        report = budget.measure(vault, today=date(2026, 2, 3))
        tail = [i for i in report.items if i.source.startswith("session log tail")]
        self.assertEqual(len(tail), 1)
        self.assertLess(tail[0].tokens, 200, "only the last 50 lines are injected")
