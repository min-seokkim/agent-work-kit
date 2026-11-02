import subprocess
import tempfile
import unittest
from pathlib import Path

from awkit.gitrepo import top_and_commit, toplevel


class TopAndCommitTests(unittest.TestCase):
    """One git process answers where the repository is and whether it has a commit."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()

    def git(self, folder, *args):
        subprocess.run(["git", "-C", str(folder), "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost",
                        *args], check=True, capture_output=True)

    @staticmethod
    def found(folder):
        # Git prints the long, forward-slash form of a path; Windows CI's temporary folder is a short name.
        top, has_commit = top_and_commit(folder)
        return top.resolve(), has_commit

    def test_outside_without_and_with_a_commit(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.assertIsNone(top_and_commit(outside))
        project = self.base / "with spaces and 한글"
        (project / "sub").mkdir(parents=True)
        self.git(project, "init", "-q")
        self.assertEqual(self.found(project / "sub"), (project, False))
        with self.assertRaisesRegex(ValueError, "no commit yet"):
            toplevel(project)
        self.git(project, "commit", "-q", "--allow-empty", "-m", "First")
        self.assertEqual(self.found(project / "sub"), (project, True))
        self.assertEqual(toplevel(project / "sub").resolve(), project)
        with self.assertRaisesRegex(ValueError, "Not a Git repository"):
            toplevel(outside)


if __name__ == "__main__":
    unittest.main()
