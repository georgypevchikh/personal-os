import json
import os
import subprocess

from personal_os import metrics, privacy
from personal_os.cli import main

from tests.helpers import VaultCase, owner_note

FAKE_GITHUB = "ghp_" + "A" * 36
FAKE_KEY = "sk-" + "b" * 40


class ScanTextTests(VaultCase):
    def test_secrets_are_detected_and_masked(self):
        findings = privacy.scan_text("x.md", f"a {FAKE_GITHUB}\nb {FAKE_KEY}\n", [])
        self.assertEqual({f.rule for f in findings}, {"secret: github token", "secret: api key (sk-)"})
        for f in findings:
            self.assertNotIn(FAKE_GITHUB, f.sample)
            self.assertNotIn(FAKE_KEY, f.sample)

    def test_email_allowlist(self):
        text = "real person@gmail.com\nfine test@example.com\nfine noreply@anthropic.com\n"
        self.assertEqual([f.line for f in privacy.scan_text("x.md", text, [])], [1])

    def test_home_paths(self):
        self.assertTrue(privacy.scan_text("x.md", "/Users/alice/Code", []))
        self.assertFalse(privacy.scan_text("x.md", "~/Code and /Users/<you>/Code", []))

    def test_denylist_is_case_insensitive_and_unicode(self):
        findings = privacy.scan_text("x.md", "Met with ALICE and Борис", ["alice", "борис"])
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f.rule == "denylisted term" for f in findings))
        self.assertNotIn("alice", " ".join(f.sample for f in findings))


class RepoScanTests(VaultCase):
    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        self.denylist = self.tmp / "denylist.txt"
        self.denylist.write_text("# private\nsecretclient\n", encoding="utf-8")

    def run_cli(self, *args: str) -> int:
        return main(["scan", "--root", str(self.repo), "--denylist", str(self.denylist), *args])

    def test_clean_repo_passes_and_dirty_repo_blocks(self):
        (self.repo / "ok.md").write_text("all good", encoding="utf-8")
        self.assertEqual(self.run_cli(), 0)
        (self.repo / "bad.md").write_text("worked for SecretClient", encoding="utf-8")
        self.assertEqual(self.run_cli(), 1)

    def test_staged_mode_reads_the_index_not_the_worktree(self):
        bad = self.repo / "note.md"
        bad.write_text(f"oops {FAKE_GITHUB}", encoding="utf-8")
        self.git(self.repo, "add", "note.md")
        bad.write_text("cleaned in worktree but not re-staged", encoding="utf-8")
        self.assertEqual(self.run_cli("--staged"), 1)

    def test_missing_denylist_blocks_unless_allowed(self):
        os.environ.pop("PRIVACY_DENYLIST", None)
        missing = str(self.tmp / "nope.txt")
        self.assertEqual(main(["scan", "--root", str(self.repo), "--denylist", missing]), 2)
        self.assertEqual(main(["scan", "--root", str(self.repo), "--denylist", missing, "--allow-missing-denylist"]), 0)


class MetricsPrivacyTests(VaultCase):
    """The metrics JSON must never contain names, paths below top level, ids or content."""

    def test_no_names_paths_ids_or_content_leak(self):
        canary_dir = "zz-canary-folder"
        blocks = [
            {"id": "meta", "kind": "system", "owner": "00-meta/current-context.md", "depends_on": ["self"]},
            {"id": "self", "kind": "domain", "owner": "10-self/_home.md", "depends_on": []},
            {"id": "canary-block-id", "kind": "project", "owner": "30-projects/canary-project/_home.md", "depends_on": []},
        ]
        vault = self.minimal_vault(blocks=blocks)
        self.write("00-meta/current-context.md", owner_note("Current Context", body="canary-block-id"))
        self.write("30-projects/canary-project/_home.md", owner_note("Canary Title", body="canary-body-word"))
        self.write(f"{canary_dir}/canary-file-name.md", "canary-content [[canary-link-target]]")
        self.write("00-meta/sessions/2026-05-01.md", "canary-session-text")
        self.write("00-meta/decisions/2026-05-02-canary-decision.md", "x")
        self.write("00-meta/agent-failure-modes.md", "## FM-001 — canary failure\n")
        subprocess.run(["git", "-C", str(self.tmp), "init", "-q"], check=True)

        blob = json.dumps(metrics.collect(vault))
        self.assertNotIn("canary", blob.lower())
        data = json.loads(blob)
        self.assertEqual(data["memory"], {**data["memory"], "session_logs": 1, "decision_logs": 1, "failure_modes": 1})
        self.assertIn("(other)", data["notes"]["by_area"], "non-standard top folders are bucketed")
        self.assertEqual(data["links"]["broken"], 1)
        graph = data["blocks"]["graph"]
        self.assertEqual([n["id"] for n in graph["nodes"]], ["S1", "D1", "P1"])
        self.assertIn(["S1", "D1"], graph["edges"])
