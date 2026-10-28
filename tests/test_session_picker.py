"""Discovery's CLI/HTTP entry points and the selectable metadata screen."""

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from awkit.cli import main
from awkit.session_http import SessionServer, request
from awkit.sessions import SessionController


class PickerRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.controller = SessionController(self.project, [sys.executable, "unused-provider.py"])
        self.addCleanup(self.controller.close)
        self.server = SessionServer(self.controller)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        (self.controller.directory / "controller.json").write_text(json.dumps(dict(
            schema=1, project=str(self.project), url=self.server.url, token=self.server.token)), encoding="utf-8")

    def test_unavailable_discovery_does_not_start_or_create(self):
        before = {str(p): p.read_bytes() for p in self.controller.directory.rglob("*") if p.is_file()}
        result = request(self.project, "discover", dict(limit=20))
        self.assertFalse(result["available"])
        self.assertEqual(result["conversations"], [])
        self.assertIsNone(self.controller.provider)
        self.assertEqual(self.controller.status()["sessions"], [])
        after = {str(p): p.read_bytes() for p in self.controller.directory.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_routes_bind_query_to_controller_project_and_reject_invalid_limits(self):
        for args in (dict(project=str(self.project.parent)), dict(limit=True), dict(limit=0), dict(limit=51)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                request(self.project, "discover", args)
        self.assertIsNone(self.controller.provider)

    def test_discovery_requires_local_origin_and_token(self):
        body = json.dumps(dict(action="discover", args={})).encode()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for headers in ({"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + self.server.token, "Origin": "https://example.invalid"}):
            headers["Content-Type"] = "application/json"
            call = urllib.request.Request(self.server.url + "/api/command", data=body, headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                opener.open(call, timeout=3)
            self.assertEqual(raised.exception.code, 403)
            raised.exception.close()
        self.assertIsNone(self.controller.provider)

    def test_cli_forwards_opaque_cursor_and_reports_unavailability(self):
        for available, expected in ((True, 0), (False, 1)):
            result = dict(available=available, project=str(self.project), conversations=[], next_cursor=None,
                          reason=None if available else "No eligible connection")
            with patch("awkit.session_http.request", return_value=result) as call, redirect_stdout(io.StringIO()) as output:
                code = main(["session", "--project", str(self.project), "discover", "--cursor", "opaque-token", "--limit", "7"])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(output.getvalue()), dict(schema=1, **result))
            call.assert_called_once_with(self.project, "discover", dict(cursor="opaque-token", limit=7))

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_screen_preserves_exact_selection_across_pages_refresh_and_refusal(self):
        from playwright.sync_api import expect, sync_playwright

        identities = [f"00000000-0000-4000-8000-{number:012d}" for number in range(1, 4)]
        rows = [dict(id=ident, name="Twin" if index < 2 else None, project=str(self.project), source="appServer",
                     created_at=1700000000, updated_at=1700000100, registered=index == 1)
                for index, ident in enumerate(identities)]
        calls = []
        enrollment = []

        def discover(*, cursor=None, limit=20):
            calls.append(dict(cursor=cursor, limit=limit))
            return dict(available=True, reason=None, project=str(self.project),
                        conversations=[rows[2]] if cursor else rows[:2], next_cursor=None if cursor else "next-page")

        def enroll(**args):
            enrollment.append(args)
            raise ValueError("The selected conversation has an active owner.")

        self.controller.discover = discover
        self.controller.enroll = enroll
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
            try:
                page = browser.new_page(viewport=dict(width=1280, height=1000))
                page.goto(self.server.url + "/#token=" + self.server.token)
                page.get_by_role("button", name="Use existing conversation", exact=True).click()
                expect(page.locator(".candidate")).to_have_count(2)
                page.locator(".candidate").first.click()
                expect(page.locator("#enroll-thread")).to_have_value(identities[0])
                page.locator("#enroll-name").fill("Review my change")
                page.get_by_role("button", name="More conversations", exact=True).click()
                expect(page.locator(".candidate")).to_have_count(1)
                expect(page.locator(".candidate strong")).to_have_text("Unnamed conversation")
                expect(page.locator("#picker-selection")).to_contain_text(identities[0])
                page.get_by_role("button", name="Refresh list", exact=True).click()
                expect(page.locator(".candidate")).to_have_count(2)
                expect(page.locator("#enroll-thread")).to_have_value(identities[0])
                expect(page.locator("#enroll-name")).to_have_value("Review my change")
                self.assertEqual(enrollment, [])
                self.assertIsNone(self.controller.provider)
                page.get_by_role("button", name="Enroll conversation", exact=True).click()
                expect(page.locator("#picker-status")).to_contain_text("active owner")
                expect(page.locator("#enroll-dialog")).to_be_visible()
                expect(page.locator("#enroll-thread")).to_have_value(identities[0])
                expect(page.locator("#enroll-name")).to_have_value("Review my change")
                self.assertEqual(enrollment, [dict(name="Review my change", thread_id=identities[0])])
                self.assertEqual(calls[:3], [dict(cursor=None, limit=20), dict(cursor="next-page", limit=20),
                                             dict(cursor=None, limit=20)])
                artifacts = os.environ.get("AWKIT_PICKER_ARTIFACTS")
                for width in (1280, 390):
                    page.set_viewport_size(dict(width=width, height=1000))
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                    self.assertFalse(page.locator("#enroll-dialog").evaluate("e => e.scrollWidth > e.clientWidth"))
                    if artifacts:
                        folder = Path(artifacts)
                        folder.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(folder / f"picker-refusal-{width}.png"), full_page=True)
                page.locator("#enroll-thread").fill(identities[2])
                expect(page.locator("#picker-selection")).to_be_hidden()
                expect(page.locator("#enroll-name")).to_have_value("Review my change")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
