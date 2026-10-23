"""Frozen full-file findings keep their policy while correspondence remains conservative."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit import checks
from awkit.review import git
from awkit.writing_compare import compare_writing, render_comparison
from support import child_env


class WritingComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "owner")
        git(self.repo, "config", "user.email", "owner@example.com")
        git(self.repo, "config", "core.autocrlf", "false")

    def commit(self, files):
        for name, text in files.items():
            path = self.repo / name
            if text is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "Fictional document revision")
        return git(self.repo, "rev-parse", "HEAD")

    def pair(self, before, after):
        baseline = self.commit({"doc.md": before})
        candidate = self.commit({"doc.md": after})
        return compare_writing(self.repo, baseline, candidate, ["doc.md"])

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "awkit", "check", *args], cwd=self.repo,
                              env=child_env(), capture_output=True, text=True, encoding="utf-8")

    def test_old_error_still_blocks_a_clean_edit_and_full_reports_remain(self):
        report = self.pair("A—B.\n", "A—B.\nA clean addition.\n")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["summary"]["introduced_total_exact"], 0)
        self.assertEqual(report["candidate_occurrences"][0]["classification"], "existing")
        self.assertIn("+A clean addition.", report["changed_regions_display_only"][0]["diff"])
        self.assertEqual(report["full_file"]["candidate"]["report"]["errors"], 1)
        self.assertTrue(render_comparison(report).startswith("Candidate full-file check: blocked"))

    def test_line_ending_display_preserves_separate_rows_and_original_hashes(self):
        for ending in ("\n", "\r\n", "\r", ""):
            with self.subTest(ending=repr(ending)):
                before, after = "Old text." + ending, "New text." + ending
                report = self.pair(before, after)
                diff = report["changed_regions_display_only"][0]["diff"]
                self.assertIn("-Old text.", diff.splitlines())
                self.assertIn("+New text.", diff.splitlines())
                self.assertEqual(diff.count("No newline at end of file"), 0 if ending else 2)
                for label, source in (("baseline", before), ("candidate", after)):
                    self.assertEqual(report["full_file"][label]["sources"][0]["sha256"],
                                     hashlib.sha256(source.encode()).hexdigest())

    def test_shift_exposure_and_introduction_use_complete_sources(self):
        cases = [
            ("A—B.\n", "A heading.\n\nA—B.\n", "existing"),
            ("A, B.\n", "A—B.\n", "introduced"),
            ("```text\nA—B.\n```\n", "A—B.\n", "introduced"),
            ("확인하십시오.\n", "확인하십시오.\n확인하세요.\n", "introduced"),
        ]
        for before, after, expected in cases:
            with self.subTest(expected=expected, after=after):
                report = self.pair(before, after)
                self.assertEqual(report["candidate_occurrences"][0]["classification"], expected)
                self.assertEqual(report["exit_code"], 1)
        exposed = self.pair("```text\nA—B.\n```\n", "A—B.\n")
        self.assertFalse(exposed["candidate_occurrences"][0]["correspondence_evidence"]
                         ["baseline_line_checked_as_prose"])

    def test_equal_global_summaries_do_not_establish_equal_witnesses(self):
        before = "이 방법을 사용하십시오.\n이 방법을 사용하세요.\n"
        after = "이 방법을 사용하십시오.\n다른 방법을 사용하세요.\n"
        report = self.pair(before, after)
        previous, current = report["baseline_inventory"][0], report["candidate_occurrences"][0]
        self.assertEqual(previous["finding"], current["finding"])
        self.assertNotEqual(previous["witness"], current["witness"])
        self.assertEqual(current["classification"], "unclassified")
        self.assertIsNone(report["summary"]["introduced_total_exact"])
        self.assertEqual(self.pair(before, before)["candidate_occurrences"][0]["classification"], "existing")
        self.assertEqual(self.pair(before, before + "A clean addition.\n")
                         ["candidate_occurrences"][0]["classification"], "unclassified")

    def test_duplicate_passages_leave_baseline_inventory_unresolved(self):
        report = self.pair("A—B.\nA—B.\n", "A—B.\n")
        self.assertEqual([x["classification"] for x in report["candidate_occurrences"]], ["unclassified"])
        self.assertEqual([x["correspondence"] for x in report["baseline_inventory"]],
                         ["unclassified", "unclassified"])
        self.assertIsNone(report["summary"]["introduced_total_exact"])

    def test_equal_same_line_payloads_keep_multiplicity_and_distinct_spans(self):
        one = "A" * 40 + "—" + "A" * 40
        report = self.pair(one + "\n", one + one + "\n")
        rows = report["candidate_occurrences"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["finding"], rows[1]["finding"])
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])
        self.assertNotEqual(rows[0]["witness"]["column_start"], rows[1]["witness"]["column_start"])
        self.assertEqual([x["classification"] for x in rows], ["unclassified", "unclassified"])
        unchanged = self.pair(one + one + "\n", one + one + "\n")
        self.assertEqual([x["classification"] for x in unchanged["candidate_occurrences"]],
                         ["existing", "existing"])

    def test_introduced_first_display_keeps_raw_order_and_warning_policy(self):
        report = self.pair("A—B.\n", "A—B.\nC—D.\n")
        rows = report["candidate_occurrences"]
        self.assertEqual([x["classification"] for x in rows], ["existing", "introduced"])
        self.assertEqual(report["reading_order"], ["candidate:1", "candidate:0"])
        text = render_comparison(report)
        self.assertLess(text.index("[introduced candidate:1]"), text.index("[existing candidate:0]"))
        warning = self.pair("A note.\n", "Here is a note.\n")
        self.assertEqual(warning["exit_code"], 0)
        self.assertEqual(warning["candidate_occurrences"][0]["finding"]["level"], "warning")

    def test_fixed_baseline_survives_later_candidates_and_user_edits(self):
        baseline = self.commit({"doc.md": "A, B.\n"})
        first = self.commit({"doc.md": "A—B.\n"})
        second = self.commit({"doc.md": "A—B.\nA user-supplied detail.\n"})
        for candidate in (first, second):
            report = compare_writing(self.repo, baseline, candidate, ["doc.md"])
            self.assertEqual(report["inputs"]["baseline"]["commit"], baseline)
            self.assertEqual(report["candidate_occurrences"][0]["classification"], "introduced")

    def test_absence_is_distinct_from_unreadable_and_unmatched_addition(self):
        baseline = self.commit({"old.md": "A—B.\n"})
        candidate = self.commit({"old.md": None, "new.md": "A—B.\n"})
        report = compare_writing(self.repo, baseline, candidate, ["old.md", "new.md"])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["candidate_occurrences"][0]["classification"], "unclassified")
        self.assertEqual(report["baseline_inventory"][0]["correspondence"], "absent-at-selected-path")
        self.assertIn("old.md: read -> absent", render_comparison(report))
        self.assertIn("new.md: absent -> read", render_comparison(report))
        deleted = compare_writing(self.repo, baseline, candidate, ["old.md"])
        self.assertEqual(deleted["exit_code"], 0)
        self.assertEqual(deleted["full_file"]["candidate"]["status"], "no-files")
        self.assertIn("Candidate full-file check: no file checked", render_comparison(deleted))
        missing = compare_writing(self.repo, baseline, candidate, ["missing.md"])
        self.assertEqual(missing["exit_code"], 2)
        self.assertIsNone(missing["summary"]["candidate_occurrences_exact"])

    def test_absent_baseline_finding_does_not_claim_accepted_correction(self):
        report = self.pair("A—B.\n", "A, B.\n")
        self.assertEqual(report["baseline_inventory"][0]["correspondence"], "absent-in-candidate-report")
        self.assertIn("absence does not establish accepted correction", render_comparison(report))

    def test_invalid_baseline_preserves_readable_candidate_findings(self):
        candidate = self.commit({"doc.md": "A—B.\n"})
        report = compare_writing(self.repo, "missing-ref", candidate, ["doc.md"])
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["full_file"]["candidate"]["report"]["errors"], 1)
        self.assertEqual(report["candidate_occurrences"][0]["classification"], "unclassified")
        self.assertIsNone(report["summary"]["introduced_total_exact"])
        invalid_candidate = compare_writing(self.repo, candidate, "--help", ["doc.md"])
        self.assertEqual(invalid_candidate["exit_code"], 2)
        self.assertIsNone(invalid_candidate["summary"]["candidate_occurrences_exact"])

    def test_unsupported_decoding_keeps_other_side_and_never_empty_passes(self):
        baseline = self.commit({"doc.md": b"\xffinvalid UTF-8\n"})
        candidate = self.commit({"doc.md": "A—B.\n"})
        report = compare_writing(self.repo, baseline, candidate, ["doc.md"])
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(len(report["candidate_occurrences"]), 1)
        self.assertEqual(report["candidate_occurrences"][0]["classification"], "unclassified")
        self.assertIsNone(report["summary"]["baseline_occurrences_exact"])
        nul = self.commit({"doc.md": b"A\x00B\n"})
        report = compare_writing(self.repo, candidate, nul, ["doc.md"])
        self.assertEqual(report["exit_code"], 2)
        self.assertIsNone(report["summary"]["candidate_occurrences_exact"])

    def test_rejects_unsafe_paths_and_keeps_git_pathspecs_literal(self):
        revision = self.commit({"doc.md": "A—B.\n", "docs/반납 안내.md": "A—B.\n"})
        for path in ("../doc.md", "a/../doc.md", "/doc.md", "C:/doc.md", "C:doc.md",
                     "a\\doc.md", "a//doc.md", "./doc.md", "a.md\0", "not-markdown.txt"):
            with self.subTest(path=path):
                report = compare_writing(self.repo, revision, revision, [path])
                self.assertEqual(report["exit_code"], 2)
        literal = compare_writing(self.repo, revision, revision, ["*.md"])
        self.assertEqual(literal["exit_code"], 2)
        supported = compare_writing(self.repo, revision, revision, ["docs/반납 안내.md"])
        self.assertEqual(supported["candidate_occurrences"][0]["classification"], "existing")
        duplicate = compare_writing(self.repo, revision, revision, ["doc.md", "doc.md"])
        self.assertEqual(duplicate["exit_code"], 2)
        self.assertEqual(len(duplicate["candidate_occurrences"]), 1)

    def test_rejects_directory_symlink_and_submodule_blobs_without_following_them(self):
        baseline = self.commit({"doc.md": "A—B.\n", "folder.md/inside.md": "A—B.\n"})
        directory = compare_writing(self.repo, baseline, baseline, ["folder.md"])
        self.assertEqual(directory["exit_code"], 2)
        # Construct Git modes directly so Windows needs no symlink privilege or external repository.
        oid = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.repo,
                             input=b"../../outside.md", capture_output=True, check=True).stdout.decode().strip()
        git(self.repo, "update-index", "--add", "--cacheinfo", f"120000,{oid},link.md")
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{baseline},module.md")
        git(self.repo, "commit", "-q", "-m", "Nonregular fictional entries")
        candidate = git(self.repo, "rev-parse", "HEAD")
        for path in ("link.md", "module.md"):
            with self.subTest(path=path):
                report = compare_writing(self.repo, baseline, candidate, [path])
                self.assertEqual(report["exit_code"], 2)
                self.assertEqual(report["full_file"]["candidate"]["sources"][0]["state"], "error")

    def test_frozen_reads_preserve_real_index_worktree_and_untracked_content(self):
        baseline = self.commit({"doc.md": "A—B.\n"})
        candidate = self.commit({"doc.md": "A—B.\nA clean addition.\n"})
        (self.repo / "doc.md").write_text("Uncommitted replacement.\n", encoding="utf-8")
        (self.repo / "staged.txt").write_text("Unrelated staged content", encoding="utf-8")
        git(self.repo, "add", "staged.txt")
        (self.repo / "untracked.txt").write_text("User work", encoding="utf-8")
        def state():
            return {p.relative_to(self.repo).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in self.repo.rglob("*") if p.is_file()}
        before = state()
        report = compare_writing(self.repo, baseline, candidate, ["doc.md"])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(before, state())
        self.assertEqual(report["inputs"]["candidate"]["commit"], candidate)
        self.assertEqual(report["checker"]["module"], str(Path(checks.__file__).resolve()))
        self.assertEqual(len(report["checker"]["loaded_function_sha256"]), 64)

    def test_new_cli_json_and_legacy_writing_contract_remain_separate(self):
        baseline = self.commit({"doc.md": "A—B.\n"})
        candidate = self.commit({"doc.md": "A—B.\nA clean addition.\n"})
        result = self.cli("writing-compare", baseline, candidate, "doc.md", "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["format"], 1)
        self.assertEqual(report["summary"]["confirmed_existing"], 1)
        legacy = self.cli("writing", "doc.md", "--json")
        self.assertEqual(legacy.returncode, 1)
        old = json.loads(legacy.stdout)
        self.assertEqual(set(old), {"files", "errors", "warnings", "findings", "ok"})
        self.assertEqual(report["full_file"]["candidate"]["report"], old)
        bad = self.cli("writing-compare", "missing", candidate, "doc.md", "--json")
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(json.loads(bad.stdout)["comparison_status"], "error")


if __name__ == "__main__":
    unittest.main()
