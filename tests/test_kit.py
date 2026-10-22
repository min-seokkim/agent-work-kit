import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from awkit.kit_install import install, install_roles, load_roles

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)\)")


# Folders that hold dependencies, build output or run records rather than managed documents.
SKIP_DIRS = {"build", "dist", "node_modules", "site-packages", "__pycache__"}


def managed_documents(folder: Path, include=None):
    """Markdown files to check: the root files plus `include` folders, or every folder
    except hidden ones and the dependency folders in SKIP_DIRS."""
    folder = folder.resolve()
    if include is not None:
        documents = list(folder.glob("*.md"))
        for name in include:
            documents.extend((folder / name).rglob("*.md"))
        return sorted(documents)
    documents = []
    for document in sorted(folder.rglob("*.md")):
        parts = document.relative_to(folder).parts[:-1]
        if any(part.startswith(".") or part in SKIP_DIRS for part in parts):
            continue
        documents.append(document)
    return documents


def broken_links(folder: Path, include=None):
    folder = folder.resolve()
    broken = []
    for document in managed_documents(folder, include):
        for target in LINK.findall(document.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            resolved = (document.parent / path).resolve()
            if not resolved.is_relative_to(folder):
                continue  # GitHub-relative links such as ../../releases point outside the tree
            if path and not resolved.exists():
                broken.append(f"{document.relative_to(folder).as_posix()} -> {target}")
    return broken


class KitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "my project"
        self.project.mkdir()

    def test_init_copies_kit_with_working_links_and_never_overwrites(self):
        target, copied = install(self.project)
        self.assertEqual(target, (self.project / "agent-work-kit").resolve())
        for name in ("README.md", "protocol.md", "templates/project.md", "templates/task.md"):
            self.assertIn(name, copied)
        self.assertEqual(broken_links(target), [])
        (target / "templates" / "project.md").write_text("작성한 적용표", encoding="utf-8")
        with self.assertRaises(ValueError):
            install(self.project)
        self.assertEqual((target / "templates" / "project.md").read_text(encoding="utf-8"), "작성한 적용표")
        second, _ = install(self.project, "agent-work-kit-new")
        self.assertTrue((second / "README.md").exists())
        self.assertEqual([p.name for p in self.project.iterdir() if p.name.startswith(".")], [])

    def test_init_preserves_project_and_third_party_license_notices(self):
        target, copied = install(self.project)
        self.assertIn("LICENSE.md", copied)
        self.assertIn("THIRD_PARTY_NOTICES.md", copied)
        self.assertEqual((target / "LICENSE.md").read_text(encoding="utf-8"),
                         (ROOT / "LICENSE").read_text(encoding="utf-8"))
        notices = (target / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertEqual(notices, (ROOT / "kit" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"))
        self.assertIn("Copyright (c) 2026 epoko77-ai", notices)
        self.assertEqual(broken_links(target), [])

    def test_init_rejects_path_names(self):
        for name in ("../escape", "a/b", "..", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                install(self.project, name)

    def test_cli_init(self):
        result = subprocess.run([sys.executable, "-m", "awkit", "kit", "init", str(self.project)],
                                capture_output=True, text=True, encoding="utf-8",
                                env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        again = subprocess.run([sys.executable, "-m", "awkit", "kit", "init", str(self.project)],
                               capture_output=True, text=True, encoding="utf-8",
                               env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(again.returncode, 2)


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()

    def test_templates_cover_the_five_roles(self):
        names = {role["name"]: role for role in load_roles()}
        self.assertEqual(set(names), {"scout", "analyst", "builder", "verifier", "writer"})
        self.assertEqual({names[n]["access"] for n in ("scout", "analyst", "verifier")}, {"read-only"})
        self.assertEqual(names["verifier"]["tier"], "judge")

    def test_claude_roles_use_tier_defaults_and_never_overwrite(self):
        written, skipped, _ = install_roles(self.project, "claude", ["standard=claude-sonnet-x"])
        self.assertEqual(len(written), 5)
        folder = self.project / ".claude" / "agents"
        scout = (folder / "scout.md").read_text(encoding="utf-8")
        self.assertIn("model: haiku", scout)
        self.assertIn("tools: Read, Grep, Glob, Bash", scout)
        builder = (folder / "builder.md").read_text(encoding="utf-8")
        self.assertIn("model: claude-sonnet-x", builder)
        self.assertNotIn("tools:", builder)
        (folder / "scout.md").write_text("내가 고친 역할", encoding="utf-8")
        written, skipped, _ = install_roles(self.project, "claude")
        self.assertEqual((len(written), len(skipped)), (0, 5))
        self.assertEqual((folder / "scout.md").read_text(encoding="utf-8"), "내가 고친 역할")
        with self.assertRaises(ValueError):
            install_roles(self.project, "claude", ["judge=opus:high"])

    def test_codex_roles_only_pin_given_tiers_and_add_top_variant(self):
        written, _, warnings = install_roles(self.project, "codex", ["judge=gpt-sol:high", "top=gpt-astra:high"])
        folder = self.project / ".codex" / "agents"
        parsed = {path.stem: tomllib.loads(path.read_text(encoding="utf-8")) for path in written}
        self.assertEqual(set(parsed), {"scout", "analyst", "builder", "verifier", "writer", "analyst_top"})
        self.assertEqual((parsed["verifier"]["model"], parsed["verifier"]["model_reasoning_effort"]), ("gpt-sol", "high"))
        self.assertEqual(parsed["analyst_top"]["name"], "analyst_top")
        self.assertEqual(parsed["analyst_top"]["model"], "gpt-astra")
        self.assertNotIn("model", parsed["scout"])
        self.assertNotIn("sandbox_mode", parsed["scout"])
        self.assertIn("scout", warnings[0])
        builder = next(role for role in load_roles() if role["name"] == "builder")
        self.assertEqual(parsed["builder"]["developer_instructions"], builder["instructions"])
        self.assertTrue((folder / "writer.toml").exists())

    def test_bad_model_specs_are_rejected(self):
        for spec in ("judge", "best=opus", "judge=", 'judge=a"b'):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                install_roles(self.project, "codex", [spec])

    def test_cli_roles(self):
        command = [sys.executable, "-m", "awkit", "kit", "roles", str(self.project), "--provider", "codex"]
        env = {**os.environ, "PYTHONUTF8": "1"}
        first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("inherit the [agents] default", first.stderr)
        again = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(again.returncode, 2)


class DocumentationTests(unittest.TestCase):
    def test_repository_links_resolve(self):
        # The documents example ships one broken link on purpose; everything else must resolve.
        self.assertEqual(broken_links(ROOT, ("docs", "kit", "examples")),
                         ["examples/first-run/documents/docs/index.md -> config.md"])

    def test_link_check_skips_dependency_folders_but_not_managed_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in (".venv/lib/site-packages/pkg", ".awkit/runs", "node_modules/x", "docs"):
                (root / folder).mkdir(parents=True)
                (root / folder / "page.md").write_text("[gone](missing.md)", encoding="utf-8")
            (root / "README.md").write_text("[docs](docs/page.md) [gone](nowhere.md)", encoding="utf-8")
            self.assertEqual(broken_links(root), ["README.md -> nowhere.md", "docs/page.md -> missing.md"])
            self.assertEqual(broken_links(root, ("docs",)), ["README.md -> nowhere.md", "docs/page.md -> missing.md"])
            self.assertEqual(broken_links(root, ()), ["README.md -> nowhere.md"])


if __name__ == "__main__":
    unittest.main()
