import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awkit import doctor as diagnostics
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
            # A kit copied by another awkit version is pointed out, and so is one with no record.
            version = project / "agent-work-kit" / "VERSION.txt"
            version.write_text("awkit: 0.0.1\n", encoding="utf-8")
            older = {f["item"]: f for f in diagnose(project)}["kit folder"]
            self.assertEqual(older["status"], "warning")
            self.assertIn("awkit 0.0.1", older["detail"])
            version.unlink()
            self.assertIn("records no version", {f["item"]: f for f in diagnose(project)}["kit folder"]["detail"])
            self.assertTrue(findings["claude skills"]["detail"].startswith(f"{len(SITUATIONS)} awkit skills"))
            self.assertIn("project repository", render(list(findings.values())))


class ConnectionDiagnostics(unittest.TestCase):
    def test_configuration_problems_are_reported_without_running_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / 'gitconfig'
            identity.write_text('[user]\nname = Owner\nemail = owner@example.invalid\n', encoding='utf-8')
            configs = {
                'missing commands': 'schema = 1\n',
                'empty list': 'schema = 1\nchecks = []\n',
                'wrong type': 'schema = 1\nchecks = "test"\n',
                'invalid TOML': 'schema = [\n',
                'empty argv': 'schema = 1\n[[checks]]\nname = "x"\nargv = []\n',
                'wrong schema': 'schema = 2\n',
                'invalid cwd': 'schema = 1\n[[checks]]\nname = "x"\nargv = ["test"]\ncwd = "../outside"\n',
            }
            for name, config in configs.items():
                with self.subTest(name=name):
                    path = root / 'checks.toml'
                    path.write_text(config, encoding='utf-8')
                    result = doctor(root, identity)
                    self.assertEqual(result.returncode, 0, result.stderr)  # warnings keep the existing exit contract
                    findings = json.loads(result.stdout)
                    check = next(f for f in findings if f['item'] == 'project checks')
                    self.assertEqual(check['status'], 'warning')
                    self.assertNotEqual(render(findings).splitlines()[-1], 'ready')
                    self.assertEqual(path.read_text(encoding='utf-8'), config)
            config = ('schema = 1\n[[checks]]\nname = "marker"\nargv = '
                      + json.dumps([sys.executable, '-c',
                                    f"from pathlib import Path; Path({str(root / 'executed')!r}).touch()"])
                      + '\n')
            (root / 'checks.toml').write_text(config, encoding='utf-8')
            findings = json.loads(doctor(root, identity).stdout)
            check = next(f for f in findings if f['item'] == 'project checks')
            self.assertEqual(check['status'], 'ok')
            self.assertIn('execution unverified', check['detail'])
            self.assertFalse((root / 'executed').exists())
            self.assertFalse((root / '.awkit').exists())

    def test_repeated_init_keeps_warning_and_existing_configuration(self):
        from awkit.connect import init
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = init(root, hooks=False, git=False)
            config = root / 'checks.toml'
            original = config.read_bytes()
            second = init(root, hooks=False, git=False)
            self.assertTrue(any('no check command' in note for note in first['notes']))
            self.assertTrue(any('no check commands' in note for note in second['notes']))
            self.assertEqual(config.read_bytes(), original)

    def test_installation_origin_never_borrows_another_distributions_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            module = Path(temporary) / 'lib' / 'awkit' / 'doctor.py'
            module.parent.mkdir(parents=True)
            module.touch()
            dist = mock.Mock()
            dist.locate_file.return_value = module
            commit = 'a' * 40
            origins = [
                (json.dumps({'url': 'https://user:secret@example.invalid/project',
                             'vcs_info': {'commit_id': commit}}), commit),
                (None, 'unavailable'),  # index or wheel installation without direct URL metadata
                ('{bad', 'unavailable'),
                ('[]', 'unavailable'),
                (json.dumps({'dir_info': {'editable': True}}), 'unavailable'),
            ]
            with mock.patch.object(diagnostics, '__file__', str(module)), \
                    mock.patch.object(diagnostics.metadata, 'distribution', return_value=dist):
                for raw, expected in origins:
                    with self.subTest(raw=raw):
                        dist.read_text.return_value = raw
                        detail = diagnostics.runtime_origin()
                        self.assertIn(expected, detail)
                        self.assertNotIn('secret', detail)
                dist.read_text.return_value = json.dumps({'vcs_info': {'commit_id': commit}})
                dist.locate_file.return_value = module.parent / 'another.py'
                self.assertNotIn(commit, diagnostics.runtime_origin())
                self.assertIn('other code', diagnostics.runtime_origin())
            with mock.patch.object(diagnostics, '__file__', str(module)), \
                    mock.patch.object(diagnostics.metadata, 'distribution',
                                      side_effect=diagnostics.metadata.PackageNotFoundError):
                self.assertIn('unavailable', diagnostics.runtime_origin())

    def test_source_checkout_origin_uses_loaded_code_and_marks_local_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            module = root / 'src' / 'awkit' / 'doctor.py'
            module.parent.mkdir(parents=True)
            module.write_text('# original\n', encoding='utf-8')
            (root / 'pyproject.toml').write_text('[project]\nname = "agent-work-kit"\n', encoding='utf-8')

            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], env=child_env(), text=True).strip()

            git('init', '-q')
            git('add', '.')
            git('-c', 'user.name=Owner', '-c', 'user.email=owner@example.invalid',
                '-c', 'core.hooksPath=disabled-hooks', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Source')
            revision = git('rev-parse', 'HEAD')
            with mock.patch.object(diagnostics, '__file__', str(module)), \
                    mock.patch.object(diagnostics.metadata, 'distribution', side_effect=AssertionError('stale metadata')):
                self.assertIn(revision, diagnostics.runtime_origin())
                self.assertIn('clean', diagnostics.runtime_origin())
                module.write_text('# changed\n', encoding='utf-8')
                self.assertIn('modified', diagnostics.runtime_origin())


if __name__ == "__main__":
    unittest.main()
