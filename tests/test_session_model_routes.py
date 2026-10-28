"""Explicit model selection across public creation controls."""

import io
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.cli import main
from awkit.session_http import SessionServer
from awkit.session_models import claude_observe
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class ModelRoutesTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_fresh_claude_only_choice_and_polling_keep_creation_inflight_lock(self):
        from playwright.sync_api import expect, sync_playwright

        with tempfile.TemporaryDirectory() as folder, patch("awkit.sessions.availability", return_value={"available": True}):
            controller = SessionController(Path(folder), ["missing-fictional-codex"])
            server = SessionServer(controller)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            entered, release = threading.Event(), threading.Event()
            calls = []

            def create(**args):
                calls.append(args)
                entered.set()
                if not release.wait(8):
                    raise ValueError("Fixture release timed out")
                raise ValueError("Fixture: no native creation performed")

            controller.create = create
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
                    try:
                        page = browser.new_page()
                        page.goto(server.url + "/#token=" + server.token)
                        page.get_by_role("button", name="Create session", exact=True).first.click()
                        expect(page.locator("#provider")).to_have_value("claude")
                        expect(page.locator("#provider option[value=codex]")).to_have_js_property("disabled", True)
                        expect(page.locator("#create-submit")).to_be_enabled()
                        self.assertEqual(calls, [])
                        page.locator("#create-name").fill("Available provider")
                        page.locator("#responsibility").fill("Invented fixture")
                        page.locator("#create-submit").click()
                        self.assertTrue(entered.wait(2))
                        page.wait_for_timeout(1800)  # The 1500ms status poll runs while creation is pending.
                        expect(page.locator("#create-submit")).to_be_disabled()
                        self.assertEqual(len(calls), 1)
                        self.assertEqual(calls[0]["provider"], "claude")
                        release.set()
                        expect(page.locator("#create-error")).to_contain_text("no native creation performed")
                        expect(page.locator("#create-submit")).to_be_enabled()
                    finally:
                        browser.close()
            finally:
                release.set()
                server.shutdown()
                server.server_close()
                controller.close()

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_single_codex_and_neither_available_have_explicit_creation_states(self):
        from playwright.sync_api import expect, sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
            try:
                for codex_available in (True, False):
                    with self.subTest(codex_available=codex_available), tempfile.TemporaryDirectory() as folder, patch(
                            "awkit.sessions.availability", return_value={"available": False, "reason": "Claude dependency unavailable"}):
                        controller = SessionController(folder, [sys.executable if codex_available else "missing-fictional-codex"])
                        server = SessionServer(controller)
                        threading.Thread(target=server.serve_forever, daemon=True).start()
                        try:
                            page = browser.new_page()
                            page.goto(server.url + "/#token=" + server.token)
                            if codex_available:
                                page.get_by_role("button", name="Create session", exact=True).first.click()
                                expect(page.locator("#provider")).to_have_value("codex")
                                expect(page.locator("#provider option[value=claude]")).to_have_js_property("disabled", True)
                                expect(page.locator("#create-submit")).to_be_enabled()
                            else:
                                expect(page.locator("#open-create")).to_be_disabled()
                                expect(page.locator("#creation-availability")).to_contain_text("No session provider is available")
                                expect(page.locator("#creation-availability")).to_contain_text("Claude dependency unavailable")
                                expect(page.locator("#open-history")).to_be_enabled()
                            self.assertFalse(controller._stores)
                            self.assertIsNone(controller.provider)
                            page.close()
                        finally:
                            server.shutdown()
                            server.server_close()
                            controller.close()
            finally:
                browser.close()

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_saved_provider_and_draft_survive_availability_change_until_explicit_choice(self):
        from playwright.sync_api import expect, sync_playwright

        with tempfile.TemporaryDirectory() as folder, patch("awkit.sessions.availability", return_value={"available": True}):
            controller = SessionController(folder, [sys.executable])
            server = SessionServer(controller)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
                    try:
                        page = browser.new_page()
                        page.goto(server.url + "/#token=" + server.token)
                        page.get_by_role("button", name="Create session", exact=True).first.click()
                        page.locator("#provider").select_option("codex")
                        page.locator("#create-model").fill("saved-codex-model")
                        page.locator("#create-effort").fill("custom-codex-effort")
                        controller.command = ["missing-fictional-codex"]
                        expect(page.locator("#provider-reason")).to_contain_text("Codex executable unavailable")
                        expect(page.locator("#provider")).to_have_value("codex")
                        expect(page.locator("#create-submit")).to_be_disabled()
                        expect(page.locator("#create-model")).to_have_value("saved-codex-model")
                        page.locator("#provider").select_option("claude")
                        expect(page.locator("#create-model")).to_have_value("")
                        page.locator("#create-model").fill("sonnet")
                        controller.command = [sys.executable]
                        expect(page.locator("#provider option[value=codex]")).to_have_js_property("disabled", False)
                        expect(page.locator("#provider")).to_have_value("claude")
                        page.locator("#provider").select_option("codex")
                        expect(page.locator("#create-model")).to_have_value("saved-codex-model")
                        expect(page.locator("#create-effort")).to_have_value("custom-codex-effort")
                        self.assertFalse(controller._stores)
                        self.assertIsNone(controller.provider)
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                controller.close()

    @unittest.skipUnless(os.environ.get("AWKIT_UI_TEST") == "1", "Set AWKIT_UI_TEST=1 with Playwright and a browser")
    def test_claude_requested_and_later_reported_values_do_not_claim_matching_effort(self):
        from playwright.sync_api import expect, sync_playwright

        with tempfile.TemporaryDirectory() as folder, patch("awkit.sessions.availability", return_value={"available": True}):
            controller = SessionController(Path(folder), [sys.executable, "unused-provider.py"])
            server = SessionServer(controller)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            store = SessionStore.create(controller.directory / "channels", name="Claude fixture", project=Path(folder),
                responsibility="Invented", generation=controller.generation, permissions={}, provider="claude")
            meta = store.metadata()
            store.update(native_id="fictional-owned-claude", state="idle", model_selection=dict(
                requested="sonnet", requested_effort="medium", creation=None, latest=None, state="submitted"))
            controller._stores[meta["id"]] = store
            controller.claude_clients[meta["id"]] = SimpleNamespace(alive=True, generation=controller.generation, close=lambda: None)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel=os.environ.get("AWKIT_BROWSER_CHANNEL"), headless=True)
                    try:
                        page = browser.new_page(viewport=dict(width=1280, height=1000))
                        page.goto(server.url + "/#token=" + server.token)
                        page.locator(".session").first.click()
                        page.get_by_text("Configuration", exact=True).click()
                        details = page.locator("#model-observation")
                        expect(details).to_contain_text("Requested model: sonnet")
                        expect(details).to_contain_text("Not yet reported")
                        expect(page.locator("#send")).to_be_enabled()
                        claude_observe(store, "claude-canonical-fixture")
                        expect(details).to_contain_text("Provider-reported model: claude-canonical-fixture")
                        expect(details).to_contain_text("Effective reasoning effort: Unverified")
                        expect(details).not_to_contain_text("Work is held")
                        expect(details).to_contain_text("Requested model: sonnet")
                        page.get_by_text("Provider capabilities", exact=True).click()
                        expect(page.locator("#provider-capabilities")).to_contain_text("Claude active-turn steering is unavailable")
                        artifacts = os.environ.get("AWKIT_PARITY_ARTIFACTS")
                        if artifacts:
                            Path(artifacts).mkdir(parents=True, exist_ok=True)
                            for width in (1280, 390):
                                page.set_viewport_size(dict(width=width, height=1000))
                                self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                                page.screenshot(path=str(Path(artifacts) / f"claude-configuration-{width}.png"), full_page=True)
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                controller.close()

    def test_cli_preserves_explicit_effort_separately_from_model(self):
        args = ["session", "create", "Reader", "--responsibility", "Invented", "--model", "fictional", "--reasoning-effort", "medium"]
        with patch("awkit.session_http.request", return_value={"session": {"state": "idle"}}) as call:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
        self.assertEqual(call.call_args.args[2]["reasoning_effort"], "medium")
        self.assertEqual(call.call_args.args[2]["model"], "fictional")

    def test_cli_selects_claude_configuration_and_unavailable_actions_explicitly(self):
        cases = [(["create", "Reader", "--responsibility", "Invented", "--provider", "claude", "--model", "sonnet", "--reasoning-effort", "high"],
                  "create", {"model": "sonnet", "reasoning_effort": "high"}),
                 (["discover", "--provider", "claude"], "discover", {}),
                 (["enroll", "Reader", "--thread-id", "fictional", "--provider", "claude"], "enroll", {})]
        for args, action, expected in cases:
            with self.subTest(action=action), patch("awkit.session_http.request", return_value={"available": False, "session": {"state": "idle"}}) as call:
                with redirect_stdout(io.StringIO()):
                    main(["session", *args])
                self.assertEqual(call.call_args.args[1], action)
                payload = call.call_args.args[2]
                self.assertEqual(payload["provider"], "claude")
                for field, value in expected.items():
                    self.assertEqual(payload[field], value)

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

        with tempfile.TemporaryDirectory() as folder, patch("awkit.sessions.availability", return_value={"available": True}):
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
                        expect(page.locator("#create-model")).to_be_enabled()
                        expect(page.locator("#create-effort")).to_be_enabled()
                        expect(page.locator("#create-model")).to_have_value("")
                        expect(page.locator("#create-effort")).to_have_value("")
                        page.locator("#create-submit").click()
                        expect(page.locator("#create-submit")).to_be_enabled()
                        self.assertEqual(calls[-1]["provider"], "claude")
                        self.assertNotIn("model", calls[-1])
                        self.assertNotIn("reasoning_effort", calls[-1])
                        page.locator("#create-model").fill("sonnet")
                        page.locator("#create-effort").fill("high")
                        page.locator("#create-submit").click()
                        expect(page.locator("#create-submit")).to_be_enabled()
                        self.assertEqual(calls[-1]["model"], "sonnet")
                        self.assertEqual(calls[-1]["reasoning_effort"], "high")
                        page.locator("#provider").select_option("codex")
                        expect(page.locator("#create-model")).to_have_value("chosen-model")
                        expect(page.locator("#create-effort")).to_have_value("medium")
                        page.locator("#provider").select_option("claude")
                        expect(page.locator("#create-model")).to_have_value("sonnet")
                        expect(page.locator("#create-effort")).to_have_value("high")
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
                        page.get_by_text("Configuration", exact=True).click()
                        details = page.locator("#model-observation")
                        for text in ("Requested model: chosen-model", "Requested reasoning effort: medium", "Provider-reported model: different-model", "changed-provider",
                                     "Provider-reported reasoning effort: Not recorded", "Work is held", "does not verify model access"):
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
                        page.get_by_role("button", name="Use existing conversation", exact=True).click()
                        page.locator("#enroll-provider").select_option("claude")
                        expect(page.locator("#picker-status")).to_contain_text("Claude conversation discovery is unavailable")
                        expect(page.locator("#enroll-submit")).to_be_disabled()
                        expect(page.locator("#enroll-thread")).to_be_disabled()
                        expect(page.locator("#picker-refresh")).to_be_disabled()
                        self.assertIsNone(controller.provider)
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                controller.close()


if __name__ == "__main__":
    unittest.main()
