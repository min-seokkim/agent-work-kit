"""Explicit model selection across public creation controls."""

import io
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from awkit.cli import main
from awkit.session_http import SessionServer
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class ModelRoutesTests(unittest.TestCase):
    def test_cli_preserves_explicit_effort_separately_from_model(self):
        args = ["session", "create", "Reader", "--responsibility", "Invented", "--model", "fictional", "--reasoning-effort", "medium"]
        with patch("awkit.session_http.request", return_value={"session": {"state": "idle"}}) as call:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
        self.assertEqual(call.call_args.args[2]["reasoning_effort"], "medium")
        self.assertEqual(call.call_args.args[2]["model"], "fictional")

    def test_cli_omits_default_model_and_preserves_explicit_identifier(self):
        for model in (None, "fixture-model:opaque"):
            args = ["session", "create", "Reader", "--responsibility", "Read invented facts"]
            if model is not None:
                args += ["--model", model]
            with patch("awkit.session_http.request", return_value={"session": {"state": "idle"}}) as call:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args), 0)
            payload = call.call_args.args[2]
            if model is None:
                self.assertNotIn("model", payload)
            else:
                self.assertEqual(payload["model"], model)

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_creation_switch_preserves_defaults_and_held_receipt_is_visible(self):
        from playwright.sync_api import expect, sync_playwright

        with tempfile.TemporaryDirectory() as folder:
            controller = SessionController(Path(folder), [sys.executable, "unused-provider.py"])
            server = SessionServer(controller)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            calls = []

            def create(**args):
                calls.append(args)
                raise ValueError("Fixture: creation not performed")

            controller.create = create
            store = SessionStore.create(controller.directory / "channels", name="Held model", project=Path(folder),
                responsibility="Fixture", generation=controller.generation, permissions={})
            store.update(model_selection=dict(requested="chosen-model", requested_effort="medium", creation=dict(model="chosen-model", provider="original"),
                latest=dict(model="different-model", provider="changed-provider", reasoning_effort=None, source="thread/resume response"),
                state="held"), error="Resumed model differs; no queued work dispatched.")
            controller._stores[store.metadata()["id"]] = store
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
                    try:
                        page = browser.new_page(viewport=dict(width=1280, height=1000))
                        page.goto(server.url + "/#token=" + server.token)
                        page.get_by_role("button", name="Create session", exact=True).first.click()
                        page.locator("#create-name").fill("Fixture reader")
                        page.locator("#responsibility").fill("Read invented facts")
                        page.locator("#create-model").fill("chosen-model")
                        page.locator("#create-effort").fill("medium")
                        page.locator("#create-submit").click()
                        expect(page.locator("#create-error")).to_be_visible()
                        expect(page.locator("#create-error")).to_contain_text("Fixture: creation not performed")
                        expect(page.locator("#create-model")).to_have_value("chosen-model")
                        expect(page.locator("#create-dialog")).to_be_visible()
                        artifacts = os.environ.get("AWKIT_MODEL_ARTIFACTS")
                        if artifacts:
                            target = Path(artifacts)
                            target.mkdir(parents=True, exist_ok=True)
                            for width in (1280, 390):
                                page.set_viewport_size(dict(width=width, height=1000))
                                page.locator("#create-error").scroll_into_view_if_needed()
                                page.screenshot(path=str(target / f"model-create-error-{width}.png"), full_page=True)
                            page.set_viewport_size(dict(width=1280, height=1000))
                        self.assertEqual(calls[-1]["model"], "chosen-model")
                        self.assertEqual(calls[-1]["reasoning_effort"], "medium")
                        expect(page.locator("#create-effort")).to_have_value("medium")
                        page.locator("#provider").select_option("claude")
                        expect(page.locator("#create-model")).to_be_disabled()
                        expect(page.locator("#create-effort")).to_be_disabled()
                        expect(page.locator("#codex-model")).to_be_hidden()
                        page.locator("#create-submit").click()
                        expect(page.locator("#create-submit")).to_be_enabled()
                        self.assertEqual(calls[-1]["provider"], "claude")
                        self.assertNotIn("model", calls[-1])
                        self.assertNotIn("reasoning_effort", calls[-1])
                        page.locator("#provider").select_option("codex")
                        page.locator("#create-model").fill("")
                        page.locator("#create-effort").fill("")
                        page.locator("#create-submit").click()
                        expect(page.locator("#create-submit")).to_be_enabled()
                        self.assertEqual(calls[-1]["provider"], "codex")
                        self.assertNotIn("model", calls[-1])
                        self.assertNotIn("reasoning_effort", calls[-1])
                        page.locator('[data-close="create-dialog"]').click()
                        page.locator(".session").filter(has=page.locator("strong", has_text="Held model")).click()
                        page.get_by_text("Model observation", exact=True).click()
                        details = page.locator("#model-observation")
                        for text in ("Requested model: chosen-model", "Requested reasoning effort: medium", "Returned model: different-model", "changed-provider",
                                     "Reasoning effort: Not recorded", "Work is held", "does not verify model access"):
                            expect(details).to_contain_text(text)
                        expect(page.locator("#send")).to_be_disabled()
                        for width in (1280, 390):
                            page.set_viewport_size(dict(width=width, height=1000))
                            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                            artifacts = os.environ.get("AWKIT_MODEL_ARTIFACTS")
                            if artifacts:
                                target = Path(artifacts)
                                target.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(target / f"model-held-{width}.png"), full_page=True)
                        self.assertIsNone(controller.provider)
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                controller.close()


if __name__ == "__main__":
    unittest.main()
