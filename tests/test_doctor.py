import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.doctor import diagnose, render
from support import child_env


def doctor(folder, global_config):
    env = child_env()
    env.update(GIT_CONFIG_GLOBAL=str(global_config), GIT_CONFIG_NOSYSTEM="1")
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        env.pop(key, None)
    return subprocess.run([sys.executable, "-m", "awkit", "doctor", str(folder), "--json"], capture_output=True,
                          text=True, encoding="utf-8", env=env)


class DoctorTests(unittest.TestCase):
    def test_missing_git_identity_is_reported_with_the_fix(self):
        # Without user.name and user.email, the commits awkit makes fail; doctor must say so first.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "gitconfig"
            config.write_text("", encoding="utf-8")
            result = doctor(root, config)
            self.assertEqual(result.returncode, 1, result.stderr)
            findings = {f["item"]: f for f in json.loads(result.stdout)}
            self.assertEqual(findings["git user.email"]["status"], "missing")
            self.assertIn("git config --global user.email", findings["git user.email"]["fix"])
            self.assertEqual(findings["python"]["status"], "ok")
            self.assertEqual(findings["project repository"]["status"], "warning")
            config.write_text("[user]\n\tname = Someone\n\temail = someone@example.com\n", encoding="utf-8")
            ready = doctor(root, config)
            self.assertEqual(ready.returncode, 0, ready.stdout)

    def test_project_folder_with_kit_and_skills(self):
        from awkit.kit_install import SITUATIONS, install, install_skills
        from awkit.review import track
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            install(project)
            track(project, [project / "agent-work-kit"], "Add the kit")  # commits with awkit's own identity
            install_skills(project, "claude")
            findings = {f["item"]: f for f in diagnose(project)}
            self.assertEqual(findings["project repository"]["status"], "ok")
            self.assertEqual(findings["kit folder"]["status"], "ok")
            self.assertTrue(findings["claude skills"]["detail"].startswith(f"{len(SITUATIONS)} of {len(SITUATIONS)}"))
            self.assertIn("project repository", render(list(findings.values())))


if __name__ == "__main__":
    unittest.main()
