"""Simulated evidence fixtures exercise coverage rules; they establish no actual inspection."""

import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from support import child_env

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "document-evidence"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, EXAMPLE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


PREVIEW = module("document_example_preview", "preview.py")
with patch.dict(sys.modules, {"preview": PREVIEW}):
    CHECKER = module("document_example_checker", "check_evidence.py")


def simulated_png(width, height):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\xff\xff" * width) * height)) + chunk(b"IEND", b""))


class DocumentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "example"
        shutil.copytree(EXAMPLE, self.root)
        PREVIEW.build(self.root)
        captures = []
        for name, width, height in (("wide", 1200, 900), ("narrow", 390, 844)):
            data = simulated_png(width, height)
            (self.root / "evidence" / (name + ".png")).write_bytes(data)
            captures.append(dict(path=f"evidence/{name}.png", viewport=dict(width=width, height=height),
                                 image_height=height, full_page=True, sha256=PREVIEW.digest(data)))
        self.render = dict(schema=1, status="performed", provenance="simulated-test",
                           inputs=PREVIEW.identities(self.root, ("evidence/preview.html", "evidence/preview.json")),
                           renderer=dict(application="simulated fixture", version="fixture-1", os="simulated",
                                         method="constructed PNG, no browser", font_conditions="no fonts rendered"),
                           captures=captures)
        self.save("render.json", self.render)
        self.review = dict(schema=1, duties={name: dict(status="performed", provenance="simulated-test",
            reviewer="test fixture, not a reader", method="constructed declaration, no review performed",
            limitations="simulated metadata only", inputs=PREVIEW.identities(self.root, inputs), findings=[])
            for name, inputs in CHECKER.DUTIES.items()})
        self.save("review.json", self.review)

    def save(self, name, value):
        (self.root / "evidence" / name).write_text(json.dumps(value, indent=2), encoding="utf-8")

    def inspect(self):
        return CHECKER.inspect(self.root, allow_simulated=True)

    def test_simulated_complete_metadata_passes_only_explicit_unit_test_mode(self):
        result, code = self.inspect()
        self.assertEqual(code, 0)
        self.assertTrue(result["simulated"])
        self.assertTrue(all(row["identities"] == "matching" for row in result["duties"].values()))
        result, code = CHECKER.inspect(self.root)
        self.assertEqual(code, 1)
        self.assertIn("simulated-evidence", [row["kind"] for row in result["diagnostics"]])
        child = subprocess.run([sys.executable, str(self.root / "check_evidence.py"), "--json"],
                               capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(child.returncode, 1)
        self.assertTrue(json.loads(child.stdout)["simulated"])

    def test_absent_review_after_other_mechanical_checks_succeed(self):
        self.assertEqual(PREVIEW.html_bytes(self.root), (self.root / "evidence/preview.html").read_bytes())
        (self.root / "evidence/review.json").unlink()
        mechanical = subprocess.run([sys.executable, str(self.root / "preview.py"), "check"],
                                    capture_output=True, env=child_env())
        self.assertEqual(mechanical.returncode, 0, mechanical.stderr)
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual({name: row["status"] for name, row in result["duties"].items()},
                         dict(source="missing", preservation="missing", rendered="missing"))
        self.assertIn("evidence/review.json", [row["location"] for row in result["diagnostics"]])

    def test_shared_style_stales_rendered_duty_without_invalidating_source_reading(self):
        before = (self.root / "note.md").read_bytes()
        with (self.root / "styles/shared.css").open("a", encoding="utf-8") as output:
            output.write("\narticle { max-width: 680px; }\n")
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual((self.root / "note.md").read_bytes(), before)
        self.assertEqual(result["duties"]["source"]["identities"], "matching")
        self.assertEqual(result["duties"]["preservation"]["identities"], "matching")
        self.assertEqual(result["duties"]["rendered"]["identities"], "mismatched")
        self.assertIn("stale-preview", [row["kind"] for row in result["diagnostics"]])

    def test_unrelated_change_leaves_selected_evidence_reusable(self):
        before = PREVIEW.identities(self.root, CHECKER.RENDERED)
        (self.root / "inputs/unrelated-source.md").write_text("Changed unrelated fictional exercise.\n", encoding="utf-8")
        result, code = self.inspect()
        self.assertEqual(code, 0)
        self.assertTrue(result["passed"])
        self.assertEqual(PREVIEW.identities(self.root, CHECKER.RENDERED), before)

    def test_unavailable_and_missing_are_independent_statuses(self):
        self.review["duties"]["rendered"] = dict(status="unavailable", reason="Fixture has no renderer.")
        self.save("review.json", self.review)
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual(result["duties"]["rendered"]["status"], "unavailable")
        self.assertEqual(result["diagnostics"], [dict(kind="unavailable", location="rendered", detail="Fixture has no renderer.")])
        self.review["duties"]["rendered"] = dict(status="missing")
        self.save("review.json", self.review)
        self.assertEqual(self.inspect()[0]["duties"]["rendered"]["status"], "missing")
        del self.review["duties"]["rendered"]
        self.save("review.json", self.review)
        self.assertEqual(self.inspect()[0]["duties"]["rendered"]["status"], "missing")

    def test_unavailable_render_cannot_be_a_successful_capture(self):
        self.save("render.json", dict(schema=1, status="unavailable", reason="No capture tool in fixture."))
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertIn("unavailable", [row["kind"] for row in result["diagnostics"]])

    def test_corrupted_output_and_wrong_input_identity_are_diagnosed(self):
        (self.root / "evidence/narrow.png").write_bytes(b"corrupted capture")
        self.review["duties"]["source"]["inputs"]["note.md"] = "f" * 64
        self.save("review.json", self.review)
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertTrue(any(row["kind"] == "changed-output" and row["location"] == "evidence/narrow.png"
                            for row in result["diagnostics"]))
        self.assertTrue(any(row["location"] == "source" and row["detail"] == "note.md"
                            for row in result["diagnostics"]))

    def test_source_change_requires_new_reading_even_with_same_note_and_render(self):
        with (self.root / "inputs/source-facts.md").open("a", encoding="utf-8") as output:
            output.write("\nA new source condition requires renewed review.\n")
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual(result["duties"]["source"]["identities"], "mismatched")
        self.assertEqual(result["duties"]["preservation"]["identities"], "mismatched")
        self.assertEqual(result["duties"]["rendered"]["identities"], "matching")

    def test_measurements_and_requirements_are_independent_of_candidate_prose(self):
        with (self.root / "inputs/measurements.csv").open(encoding="utf-8", newline="") as source:
            pairs = [(int(row["before_ms"]), int(row["after_ms"])) for row in csv.DictReader(source)]
        self.assertEqual(pairs, [(120, 84), (100, 80), (140, 98), (160, 112)])
        requirements = json.loads((self.root / "requirements.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(row[0] for row in pairs) / 4, requirements["derived_values"]["before_mean_ms"])
        self.assertEqual(sum(row[1] for row in pairs) / 4, requirements["derived_values"]["after_mean_ms"])

    def test_hashes_do_not_complete_an_absent_reading_declaration(self):
        self.review["duties"]["source"] = dict(status="missing", inputs=PREVIEW.identities(self.root, PREVIEW.SOURCE))
        self.save("review.json", self.review)
        self.assertEqual(self.inspect()[1], 1)

    def test_declared_unresolved_finding_prevents_pass(self):
        self.review["duties"]["preservation"]["findings"] = [dict(status="unresolved", detail="A condition needs review.")]
        self.save("review.json", self.review)
        result, code = self.inspect()
        self.assertEqual(code, 1)
        self.assertEqual(result["diagnostics"][0]["kind"], "unresolved-finding")

    def test_records_cannot_choose_paths_commands_or_duties(self):
        for name in ("../secret", "C:/secret", "inputs/../note.md", "inputs\\source-facts.md", "https://example.com"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                PREVIEW.path(self.root, name)
        self.review["duties"]["source"]["inputs"]["../private"] = "a" * 64
        self.save("review.json", self.review)
        with self.assertRaises(ValueError):
            self.inspect()
        self.review["duties"]["arbitrary-command"] = dict(status="performed")
        self.save("review.json", self.review)
        with self.assertRaises(ValueError):
            self.inspect()

    def test_schema_and_status_errors_exit_two(self):
        self.save("review.json", dict(schema=99))
        child = subprocess.run([sys.executable, str(self.root / "check_evidence.py"), "--json"],
                               capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(child.returncode, 2)
        self.assertEqual(json.loads(child.stdout)["diagnostics"][0]["kind"], "invalid")

    def test_linked_input_cannot_expand_the_boundary(self):
        selected = self.root / "inputs/source-facts.md"
        outside = Path(self.temp.name) / "outside.md"
        selected.rename(outside)
        try:
            selected.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        with self.assertRaises(ValueError):
            self.inspect()

    def test_check_is_read_only_and_build_never_manufactures_reviews(self):
        def hashes():
            return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.root.rglob("*") if path.is_file()}
        before = hashes()
        self.inspect()
        self.inspect()
        self.assertEqual(hashes(), before)
        review = (self.root / "evidence/review.json").read_bytes()
        PREVIEW.build(self.root)
        self.assertEqual((self.root / "evidence/review.json").read_bytes(), review)

    def test_generator_escapes_note_markup_and_rejects_external_css(self):
        (self.root / "note.md").write_text("# Sample\n\n<script>alert(1)</script>\n", encoding="utf-8")
        data = PREVIEW.html_bytes(self.root)
        self.assertIn(b"&lt;script&gt;", data)
        self.assertNotIn(b"<script>", data)
        (self.root / "styles/shared.css").write_text('@import "https://example.com/style";', encoding="utf-8")
        with self.assertRaises(ValueError):
            PREVIEW.build(self.root)


if __name__ == "__main__":
    unittest.main()
