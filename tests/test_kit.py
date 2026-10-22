import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from awkit import __version__
from awkit.kit_install import SITUATIONS, WORKFLOW, install, install_roles, install_skills, load_roles, read_version
from awkit.review import track
from support import child_env

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)\)")


# Folders that hold dependencies, build output or run records rather than managed documents.
SKIP_DIRS = {"build", "dist", "node_modules", "site-packages", "__pycache__"}
# Upper bounds on the kit's length by when a file is read; see docs/development.md. The files read at
# the start of every session together stay within what Claude Code's documentation recommends for
# CLAUDE.md (about 200 lines). Every other file is read when its situation arises and stays within what
# survives a context compaction whole (5,000 tokens, about 3,500 English words).
EVERY_SESSION = ("README.md", "workflow.md", "templates/project.md")
EVERY_SESSION_WORD_LIMIT = 2_000
SITUATION_FILE_WORD_LIMIT = 3_500
# Reference documents are looked up in part, when a command or a guard points to them, never read whole.
REFERENCES = ("reference.md", "failures.md")
REFERENCE_WORD_LIMIT = 9_000
LICENSES = ("LICENSE.md", "THIRD_PARTY_NOTICES.md")


def skill_front_matter(text):
    """The front matter of a SKILL.md as both agents read it: YAML keys, values plain or double-quoted."""
    if not text.startswith("---\n"):
        raise AssertionError("no front matter")
    head = text[4:].split("\n---\n", 1)[0]
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(": ")
        if not sep or not re.match(r"^[a-z][a-z0-9_-]*$", key):
            raise AssertionError(f"not a YAML mapping line: {line}")
        meta[key] = json.loads(value) if value.startswith('"') else value
    return meta


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
    # Path ordering is case-insensitive on Windows; sort the strings so the order is the same everywhere.
    return sorted(broken)


class KitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "my project"
        self.project.mkdir()

    def test_init_copies_kit_with_working_links_and_never_overwrites(self):
        target, copied = install(self.project)
        self.assertEqual(target, (self.project / "agent-work-kit").resolve())
        for name in ("README.md", "protocol.md", "templates/project.md", "templates/task.md", "VERSION.txt"):
            self.assertIn(name, copied)
        # Which kit this is: run from the source checkout, the record names its commit.
        record = read_version(target)
        self.assertEqual((record["awkit"], record["source"]), (__version__, "checkout"))
        self.assertRegex(record.get("commit", ""), r"^[0-9a-f]{40}$")
        self.assertIn(record["uncommitted kit changes"], ("yes", "no"))
        self.assertEqual(broken_links(target), [])
        (target / "templates" / "project.md").write_text("작성한 적용표", encoding="utf-8")
        with self.assertRaises(ValueError):
            install(self.project)
        self.assertEqual((target / "templates" / "project.md").read_text(encoding="utf-8"), "작성한 적용표")
        second, _ = install(self.project, "agent-work-kit-new")
        self.assertTrue((second / "README.md").exists())
        # Tracking, as the CLI does it, makes the project a repository with only the kit committed.
        self.assertEqual([p.name for p in self.project.iterdir() if p.name.startswith(".")], [])
        record = track(self.project, [target], "Add agent-work-kit")
        self.assertEqual((record["created"], record["committed"]), (True, True))
        self.assertEqual([p.name for p in self.project.iterdir() if p.name.startswith(".")], [".git"])
        log = subprocess.run(["git", "-C", str(self.project), "log", "--oneline"], capture_output=True,
                             text=True, encoding="utf-8")
        self.assertEqual(log.stdout.count("\n"), 1)
        tracked = subprocess.run(["git", "-C", str(self.project), "ls-files"], capture_output=True,
                                 text=True, encoding="utf-8").stdout
        self.assertIn("agent-work-kit/README.md", tracked)
        self.assertNotIn("agent-work-kit-new/README.md", tracked)  # only the named folder is committed
        # A second kit folder inside the repository that now has history is committed the same way.
        again = track(self.project, [second], "Add agent-work-kit-new")
        self.assertEqual((again["created"], again["committed"]), (False, True))
        self.assertEqual(track(self.project, [second], "Nothing")["skipped"], "nothing to commit")

    def test_init_without_tracking_leaves_the_folder_untracked(self):
        install(self.project)
        self.assertEqual([p.name for p in self.project.iterdir() if p.name.startswith(".")], [])
        plain = subprocess.run([sys.executable, "-m", "awkit", "kit", "init", str(self.project), "--copy", "--name", "k"],
                               capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertIn("is not in a Git repository; nothing was committed", plain.stderr)
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

    def test_cli_init_copy(self):
        result = subprocess.run([sys.executable, "-m", "awkit", "kit", "init", str(self.project), "--copy"],
                                capture_output=True, text=True, encoding="utf-8",
                                env=child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / "agent-work-kit" / "workflow.md").is_file())
        again = subprocess.run([sys.executable, "-m", "awkit", "kit", "init", str(self.project), "--copy"],
                               capture_output=True, text=True, encoding="utf-8",
                               env=child_env())
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

    def test_skills_point_to_a_copied_kit_folder(self):
        target, _ = install(self.project)
        readme = (target / "README.md").read_text(encoding="utf-8")
        for provider, folder in (("claude", ".claude/skills"), ("codex", ".agents/skills")):
            result = install_skills(self.project, provider)
            self.assertEqual((len(result["created"]), result["kept"]), (len(SITUATIONS), []))
            for name, guide, description, _ in SITUATIONS:
                text = (self.project / folder / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith(f"---\nname: {name}\ndescription: \""), text)
                quoted = text.split("\n")[2].removeprefix("description: ")
                self.assertEqual(json.loads(quoted), description)  # valid YAML: a double-quoted scalar
                self.assertIn(f"`agent-work-kit/{guide}`", text)
                self.assertTrue((target / guide).is_file(), guide)
                self.assertIn(f"]({guide})", readme)
                self.assertIn(f"`{name}`", readme)
            again = install_skills(self.project, provider)
            self.assertEqual((again["created"], again["updated"], len(again["unchanged"])), ([], [], len(SITUATIONS)))
            self.assertFalse((self.project / folder / "awkit-connect").exists())  # workflow.md points there
            self.assertFalse((self.project / folder / "awkit-workflow").exists())  # read from the kit folder
        self.assertIn("korean-writing.md", (self.project / ".claude/skills/awkit-writing/SKILL.md").read_text("utf-8"))
        (self.project / "elsewhere").mkdir()
        with self.assertRaisesRegex(ValueError, "No kit folder"):
            install_skills(self.project / "elsewhere", "claude", self.project / "elsewhere")
        # A file with an awkit skill's name that awkit did not write is kept, and the command says so.
        mine = self.project / ".agents/skills/awkit-writing/SKILL.md"
        mine.write_text("---\nname: awkit-writing\ndescription: mine\n---\nmine\n", encoding="utf-8")
        self.assertEqual(install_skills(self.project, "codex")["kept"], [mine.resolve()])

    def test_self_contained_skills_hold_the_guides_and_parse_for_both_agents(self):
        for provider, folder in (("claude", ".claude/skills"), ("codex", ".agents/skills")):
            result = install_skills(self.project, provider)
            self.assertEqual(len(result["created"]), len(SITUATIONS) + 1)
            for name, guide, description, _ in (WORKFLOW, *SITUATIONS):
                text = (self.project / folder / name / "SKILL.md").read_text(encoding="utf-8")
                meta = skill_front_matter(text)
                # Claude Code and Codex both read name and description; Codex limits them to 64 and 1024
                # characters and the name to lowercase letters, digits and hyphens.
                self.assertEqual(set(meta), {"name", "description"})
                self.assertEqual(meta["name"], name)
                self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
                self.assertEqual(meta["description"], description)
                self.assertLessEqual(len(description), 1024)
                self.assertNotIn("\n", description)
                # One line, short: agents keep every description in context.
                self.assertLessEqual(len(description.split()), 16, name)
                heading = next(line for line in (ROOT / "kit" / guide).read_text("utf-8").splitlines() if line.startswith("# "))
                self.assertIn(heading, text)
                # No link points at a kit file the skill folder does not have.
                for target in LINK.findall(text):
                    self.assertRegex(target, r"^https?://", f"{name}: {target}")
            self.assertEqual(broken_links(self.project / folder.split("/")[0]), [])
        writing = (self.project / ".claude/skills/awkit-writing/SKILL.md").read_text("utf-8")
        self.assertIn("# Korean Writing Guide", writing)  # the supplement is inside, one level down
        self.assertIn("Copyright (c) 2026 epoko77-ai", writing)  # the adapted material keeps its notice
        self.assertIn("Copyright (c) 2026 min-seokkim", writing)
        records = (self.project / ".claude/skills/awkit-records/SKILL.md").read_text("utf-8")
        self.assertIn("## Template: checkpoint.md", records)
        self.assertIn("Connect the Kit to a Project",
                      (self.project / ".claude/skills/awkit-workflow/SKILL.md").read_text("utf-8"))

    def test_a_method_bundle_leaves_out_planning_review_and_delegation(self):
        skills = self.project / ".claude" / "skills"
        for name in ("brainstorming", "writing-plans", "requesting-code-review"):
            (skills / name).mkdir(parents=True)
            (skills / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8")
        result = install_skills(self.project, "claude")
        made = {path.parent.name for path in result["created"]}
        self.assertEqual(made, {"awkit-workflow", "awkit-writing", "awkit-checking", "awkit-delivery"})
        self.assertEqual({name for name, _ in result["omitted"]},
                         {"awkit-work-types", "awkit-delegation", "awkit-review-session", "awkit-records"})
        self.assertTrue(all(reason.startswith("superpowers (skills ") for _, reason in result["omitted"]))

    def test_cli_roles(self):
        command = [sys.executable, "-m", "awkit", "kit", "roles", str(self.project), "--provider", "codex"]
        env = child_env()
        first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("inherit the [agents] default", first.stderr)
        again = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(again.returncode, 2)


def guard_map():
    spec = importlib.util.spec_from_file_location("guard_map", ROOT / "scripts" / "guard_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GuardTableTests(unittest.TestCase):
    def test_every_guard_names_entries_and_the_table_is_current(self):
        # Each guide section and each awkit command declares the catalogue entries it guards; the table
        # in kit/failures.md is built from those declarations, never kept by hand.
        module = guard_map()
        problems, table = module.build()
        self.assertEqual(problems, [])
        self.assertEqual(module.current_table(), table,
                         "kit/failures.md is out of date: run python scripts/guard_map.py --write")


class DocumentationTests(unittest.TestCase):
    def test_repository_links_resolve(self):
        # The documents example ships one broken link on purpose; everything else must resolve.
        self.assertEqual(broken_links(ROOT, ("docs", "kit", "examples")),
                         ["examples/first-run/documents/docs/index.md -> config.md"])

    def test_kit_files_stay_within_the_word_limits(self):
        counts = {path.relative_to(ROOT / "kit").as_posix(): len(path.read_text(encoding="utf-8").split())
                  for path in (ROOT / "kit").rglob("*.md") if path.name not in LICENSES}
        every_session = sum(counts.pop(name) for name in EVERY_SESSION)
        for name in REFERENCES:
            words = counts.pop(name)
            self.assertLessEqual(words, REFERENCE_WORD_LIMIT, f"kit/{name} has {words} words")
        self.assertLessEqual(every_session, EVERY_SESSION_WORD_LIMIT,
                             f"the files read every session have {every_session} words")
        for name, words in counts.items():
            self.assertLessEqual(words, SITUATION_FILE_WORD_LIMIT, f"kit/{name} has {words} words")

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
