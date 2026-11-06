"""A damaged channel cannot hide healthy sessions or be changed by startup migration."""

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class CorruptChannelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        self.command = [sys.executable, str(Path(__file__).with_name("session_provider_fixture.py"))]

    def controller(self):
        controller = SessionController(self.project, self.command)
        self.addCleanup(controller.close)
        return controller

    def test_bad_header_is_visible_and_healthy_session_can_complete_work(self):
        owner = self.controller()
        owner.create(name="Healthy", responsibility="Fictional test")
        owner.close()
        damaged = self.project / ".awkit/sessions/channels/broken.sqlite3"
        damaged.write_bytes(b"deliberately damaged database")
        before = damaged.read_bytes()
        owner = self.controller()
        views = owner.status()["sessions"]
        unavailable = next(view for view in views if view["session"]["state"] == "unavailable")
        self.assertIn(str(damaged), unavailable["control_reason"])
        self.assertFalse(unavailable["can_send"])
        self.assertEqual(damaged.read_bytes(), before)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            good = next(view for view in owner.status()["sessions"] if view["session"]["name"] == "Healthy")
            if good["can_send"]:
                break
            time.sleep(0.02)
        self.assertTrue(good["can_send"])
        owner.send("Healthy", key="healthy-work", body="Fictional request")
        while time.monotonic() < deadline:
            good = owner.status(session="Healthy")["sessions"][0]
            if len(good["messages"]) == 2:
                break
            time.sleep(0.02)
        self.assertEqual(len(good["messages"]), 2)
        self.assertEqual(damaged.read_bytes(), before)

    def test_damaged_message_page_is_rejected_before_upgrade_writes(self):
        directory = self.project / ".awkit/sessions/channels"
        store = SessionStore.create(directory, name="Damaged", project=self.project, responsibility="Fixture",
                                    generation="old", permissions={})
        store.post("message", "Fictional retained text")
        conn = sqlite3.connect(store.path)
        try:
            page = conn.execute("select rootpage from sqlite_master where name='messages'").fetchone()[0]
            size = conn.execute("pragma page_size").fetchone()[0]
            conn.execute("update awkit_session set schema=3")
            conn.commit()
        finally:
            conn.close()
        payload = bytearray(store.path.read_bytes())
        payload[(page - 1) * size] = 255
        store.path.write_bytes(payload)
        self.assertEqual(store.metadata()["name"], "Damaged")
        before = store.path.read_bytes()
        owner = self.controller()
        self.assertEqual(len(owner.status()["sessions"]), 1)
        self.assertEqual(owner.status()["sessions"][0]["session"]["state"], "unavailable")
        self.assertEqual(store.path.read_bytes(), before)

    def test_damage_after_startup_does_not_kill_dispatch_or_all_status(self):
        owner = self.controller()
        owner.create(name="Healthy", responsibility="Fictional test")
        owner.create(name="Damaged", responsibility="Fictional test")
        store = owner.store("Damaged")
        with owner.guard:
            store.path.write_bytes(b"deliberately damaged database")
        time.sleep(0.8)
        self.assertTrue(owner._worker.is_alive())
        report = owner.status()
        self.assertEqual(len(report["sessions"]), 2)
        self.assertEqual(sum(view["session"]["state"] == "unavailable" for view in report["sessions"]), 1)
        self.assertTrue(owner.status(session="Healthy")["sessions"][0]["can_send"])
