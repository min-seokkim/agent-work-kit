from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from awkit.ui import capture, load_config, sheet


class UITests(unittest.TestCase):
    def test_sheet_escapes_labels(self):
        html = sheet([{"name": "<script>alert(1)</script>", "width": 320, "issues": [], "image": "page-01-320.png"}])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("page-01-320.png", html)

    def test_invalid_config(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ui.json"
            for update in ({"base_url": "https://user:secret@example.com"}, {"widths": []},
                           {"pages": [{"name": "Other", "path": "//example.com/"}]}, {"widths": [True]}):
                config = {"base_url": "http://127.0.0.1:8000", "pages": [{"name": "Home", "path": "/"}]}
                config.update(update)
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(update=update), self.assertRaises(ValueError):
                    load_config(path)

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_capture_local_fixture_and_overflow_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.html").write_text('<meta charset="utf-8"><h1>화면 검사</h1><button>확인</button>', encoding="utf-8")
            (root / "bad.html").write_text('<h1>Overflow fixture</h1><button style="margin-left:1600px">Outside</button>', encoding="utf-8")
            (root / "blocked.html").write_text('<h1>Restricted fixture</h1><img src="https://example.invalid/asset.png"><script>fetch("/mutation", {method:"POST"}).catch(()=>{});</script>', encoding="utf-8")
            class QuietHandler(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                config = root / "ui.json"
                config.write_text(json.dumps({"base_url": f"http://127.0.0.1:{server.server_port}", "widths": [320, 1440],
                                             "pages": [{"name": "정상", "path": "/good.html"}, {"name": "넘침", "path": "/bad.html"}, {"name": "차단", "path": "/blocked.html"}]}), encoding="utf-8")
                result = capture(config, root / "output", os.environ.get("AWKIT_BROWSER_CHANNEL"))
                self.assertEqual(result["status"], "failed")
                self.assertEqual(len(result["captures"]), 6)
                self.assertEqual(result["captures"][0]["issues"], [])
                self.assertIn("horizontal-overflow", result["captures"][2]["issues"])
                self.assertIn("resource-blocked", result["captures"][4]["issues"])
                self.assertTrue((root / "output" / "sheet.png").is_file())
                self.assertEqual(len(list((root / "output").glob("page-*.png"))), 6)
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


if __name__ == "__main__":
    unittest.main()
