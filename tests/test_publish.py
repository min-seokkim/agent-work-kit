import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit.publish import Publisher


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "build"
        self.source.mkdir()
        self.output = self.root / "published"
        self.publisher = Publisher(self.output, "sample")
        self.index = self.source / "index.html"
        self.index.write_text('<h1 id="intro">안내</h1><a href="guide.html#use">사용법</a><link rel="stylesheet" href="style.css">', encoding="utf-8")
        (self.source / "guide.html").write_text('<h1 id="use">사용법</h1><a href="index.html">처음</a>', encoding="utf-8")
        (self.source / "style.css").write_text("body{color:#123}", encoding="utf-8")
        self.files = ["index.html", "guide.html", "style.css"]

    def test_publish_deduplicate_update_and_restore(self):
        a = self.publisher.publish(self.source, self.files)["version"]
        self.assertEqual(a, self.publisher.publish(self.source, list(reversed(self.files)))["version"])
        self.index.write_text("<h1>Updated</h1>", encoding="utf-8")
        b = self.publisher.publish(self.source, self.files)["version"]
        self.assertNotEqual(a, b)
        self.assertIn(b, (self.output / "index.html").read_text(encoding="utf-8"))
        self.publisher.restore(a)
        self.assertIn(a, (self.output / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(len(list((self.output / "versions").iterdir())), 2)

    def test_missing_link_anchor_and_css_resource_preserve_entry(self):
        self.publisher.publish(self.source, self.files)
        before = (self.output / "index.html").read_bytes()
        for content in ('<a href="absent.html">Missing</a>', '<a href="guide.html#absent">Missing</a>',
                        '<style>body{background:url(missing.png)}</style>', '<script src="https://example.com/a.js"></script>'):
            self.index.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.publisher.publish(self.source, self.files)
            self.assertEqual((self.output / "index.html").read_bytes(), before)

    def test_traversal_and_reserved_manifest_rejected(self):
        for path in ("../secret.txt", "/secret.txt", "folder/../secret", "manifest.json", "C:/secret", ".git/config"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.publisher.publish(self.source, ["index.html", path])

    def test_tampering_blocks_restore(self):
        version = self.publisher.publish(self.source, self.files)["version"]
        (self.output / "versions" / version / "style.css").write_text("modified", encoding="utf-8")
        before = (self.output / "index.html").read_bytes()
        with self.assertRaises(ValueError):
            self.publisher.restore(version)
        self.assertEqual((self.output / "index.html").read_bytes(), before)

    def test_extra_file_and_wrong_project_block_restore(self):
        version = self.publisher.publish(self.source, self.files)["version"]
        with self.assertRaises(ValueError):
            Publisher(self.output, "other").restore(version)
        (self.output / "versions" / version / "unexpected.txt").touch()
        with self.assertRaises(ValueError):
            self.publisher.restore(version)

    def test_atomic_switch_failure_preserves_previous_version(self):
        self.publisher.publish(self.source, self.files)
        before = (self.output / "index.html").read_bytes()
        self.index.write_text("<h1>New</h1>", encoding="utf-8")
        with patch("awkit.publish.os.replace", side_effect=OSError("simulated switch failure")), self.assertRaises(OSError):
            self.publisher.publish(self.source, self.files)
        self.assertEqual((self.output / "index.html").read_bytes(), before)
        self.assertFalse(list(self.output.glob(".entry-*")))

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("existing", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.publisher.publish(self.source, self.files)
        self.assertEqual((self.output / "index.html").read_text(), "existing")

    def test_linked_source_rejected(self):
        self.index.unlink()
        try:
            self.index.symlink_to(self.source / "guide.html")
        except OSError:
            self.skipTest("Symbolic link creation is unavailable")
        with self.assertRaises(ValueError):
            self.publisher.publish(self.source, self.files)

    def test_external_hyperlink_is_allowed_but_absolute_resource_is_not(self):
        self.index.write_text('<a href="https://example.com">Reference</a>', encoding="utf-8")
        self.publisher.publish(self.source, self.files)
        self.index.write_text('<img src="/asset.png">', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.publisher.publish(self.source, self.files)


if __name__ == "__main__":
    unittest.main()
