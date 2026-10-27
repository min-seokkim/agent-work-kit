import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("evidence_catalog", Path(__file__).resolve().parents[1] / "scripts/evidence_catalog.py")
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


class EvidenceCatalogueTests(unittest.TestCase):
    def test_shared_missing_unreferenced_and_interrupted_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path, content in {
                "docs/tasks/one.md": "`.awkit/handoffs/shared/`, `.awkit/handoffs/absent/` and `.awkit/handoffs/note.md`",
                "docs/history/tasks/two.md": "`.awkit/handoffs/shared/receipt.json`",
                "docs/evidence.md": "`.awkit/reviews/review-*/` is a pattern",
                ".awkit/handoffs/shared/fixture.txt": "retain",
                ".awkit/handoffs/unreferenced/input.txt": "retain too",
                ".awkit/handoffs/note.md": "standalone evidence",
                ".awkit/reviews/review-incomplete/result.json": json.dumps({"status": "running", "snapshot": "a" * 40}),
                ".awkit/workspaces/kept/.awkit/reviews/review-failed/result.json": json.dumps({"status": "failed", "snapshot": "b" * 40}),
            }.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = catalog.catalogue(root)
            groups = {entry["path"]: entry for entry in result["collections"]}
            self.assertEqual(groups[".awkit/handoffs/shared"]["records"], ["docs/tasks/one.md", "docs/tasks/two.md"])
            self.assertEqual(groups[".awkit/handoffs/absent"]["availability"], "missing")
            self.assertEqual(groups[".awkit/handoffs/note.md"]["kind"], "file")
            self.assertEqual(groups[".awkit/handoffs/note.md"]["files"], 1)
            self.assertEqual(groups[".awkit/handoffs/unreferenced"]["records"], [])
            self.assertNotIn(".awkit/reviews/review-", groups)
            self.assertEqual(groups[".awkit/reviews/review-incomplete"]["runs"][0]["recorded_status"], "running")
            self.assertEqual(groups[".awkit/workspaces/kept"]["runs"][0]["recorded_status"], "failed")
            catalog.write_catalogue(root, result)
            self.assertEqual(before, {name: Path(name).read_bytes() for name in before})
            self.assertIn("../../docs/tasks/two.md", (root / ".awkit/evidence/index.md").read_text(encoding="utf-8"))

    def test_linked_collections_and_outputs_are_never_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collection = root / ".awkit/handoffs/linked"
            collection.mkdir(parents=True)
            real_linked = catalog.linked
            with patch.object(catalog, "linked", side_effect=lambda path: path == collection or real_linked(path)):
                result = catalog.catalogue(root)
                self.assertEqual(result["collections"][0]["availability"], "linked")
                self.assertEqual(result["collections"][0]["files"], 0)
            output = root / ".awkit/evidence"
            output.mkdir()
            with patch.object(catalog, "linked", side_effect=lambda path: path == output or real_linked(path)):
                with self.assertRaises(ValueError):
                    catalog.write_catalogue(root, result)
            self.assertEqual(list(output.iterdir()), [])

    def test_malformed_and_unreadable_runs_remain_inspection_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / ".awkit/reviews/review-bad"
            folder.mkdir(parents=True)
            (folder / "result.json").write_text("{unfinished", encoding="utf-8")
            result = catalog.inventory(root, folder)
            self.assertEqual(result["availability"], "partial")
            self.assertEqual(result["runs"], [])
            self.assertEqual(result["issues"][0]["error"], "JSONDecodeError")
            with patch.object(catalog, "safe_path", side_effect=PermissionError):
                result = catalog.inventory(root, folder)
            self.assertEqual(result["availability"], "unreadable")


if __name__ == "__main__":
    unittest.main()
