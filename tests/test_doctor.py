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


class ProjectRulesDiagnostics(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'project'
        self.root.mkdir()

    def write_rules(self, kit='missing-guides', body=None):
        if body is None:
            body = ('[[rules]]\nname = "custom"\nkind = "inject"\n'
                    'message = "Read {kit}/writing.md."\n')
        text = '# Preserve this custom comment.\nschema = 1\n'
        if kit is not None:
            text += 'kit = ' + json.dumps(str(kit)) + '\n'
        path = self.root / 'rules.toml'
        path.write_text(text + body, encoding='utf-8')
        return path

    def findings(self):
        path = self.root / 'rules.toml'
        before = (path.read_bytes(), path.stat().st_mtime_ns) if path.is_file() else None
        found = []

        def add(item, status, detail, fix=''):
            found.append({'item': item, 'status': status, 'detail': detail, 'fix': fix})

        with mock.patch('awkit.hooks.evaluate', side_effect=AssertionError('rules must not be evaluated')), \
                mock.patch('awkit.hooks.run_command', side_effect=AssertionError('commands must not run')):
            diagnostics._rules(self.root, add)
        if before is not None:
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertFalse((self.root / '.awkit').exists())
        for finding in found:
            self.assertEqual(set(finding), {'item', 'status', 'detail', 'fix'})
        return {finding['item']: finding for finding in found}

    def test_consumption_follows_expansion_and_possible_failure_citations(self):
        cases = [
            ('[[rules]]\nname="x"\nkind="inject"\nmessage="Read {kit}/writing.md."\n', True),
            ('[[rules]]\nname="x"\nkind="verify"\ncommand=["not-run", "{kit}/check.py"]\n', True),
            ('[[rules]]\nname="x"\nkind="verify"\ncommand="{kit}/not-run"\n', True),
            ('[[rules]]\nname="x"\nkind="block"\nmessage="Custom block."\nprevents=["F29"]\n', True),
            ('[[rules]]\nname="x"\nkind="inject"\nmessage="Literal note."\nprevents=["F29"]\n', False),
            ('[[rules]]\nname="x"\nkind="inject"\nmessage="Literal note."\npaths=["{kit}/x"]\n', False),
            ('[[rules]]\nname="x"\nkind="verify"\nevents=["SessionStart"]\n'
             'command=["not-run"]\nprevents=["F29"]\n', False),
        ]
        for body, consumed in cases:
            with self.subTest(body=body):
                self.write_rules("MultiplexedPath('fictional/kit')", body)
                found = self.findings()
                self.assertEqual(found['project rules']['status'], 'ok')
                self.assertEqual('rules kit directory' in found, consumed)
                if consumed:
                    self.assertEqual(found['rules kit directory']['status'], 'warning')
                    self.assertIn('does not exist', found['rules kit directory']['detail'])

    def test_relative_absolute_default_and_literal_directories(self):
        for name in ('guides', 'agent-work-kit', "MultiplexedPath('literal')"):
            (self.root / name).mkdir()
        for value in ('guides', self.root / 'guides', None, "MultiplexedPath('literal')"):
            with self.subTest(value=value):
                self.write_rules(value)
                finding = self.findings()['rules kit directory']
                self.assertEqual(finding['status'], 'ok')
                self.assertIn('directory exists', finding['detail'])
                self.assertIn('individual guides, freshness and client loading unverified', finding['detail'])

    def test_missing_default_and_non_directory_are_warnings_with_targeted_fix(self):
        self.write_rules(None)
        missing = self.findings()['rules kit directory']
        self.assertEqual(missing['status'], 'warning')
        self.assertIn('does not exist', missing['detail'])
        (self.root / 'guide-file').write_text('not a directory', encoding='utf-8')
        self.write_rules('guide-file')
        finding = self.findings()['rules kit directory']
        self.assertIn('not a directory', finding['detail'])
        self.assertIn('correct only kit', finding['fix'])
        self.assertIn('preserve custom rules/comments', finding['fix'])
        self.assertIn('does not repair preserved project rules', finding['fix'])

    def test_invalid_rules_keep_read_decode_parse_schema_and_rule_errors_separate(self):
        cases = [
            (b'\xff', 'decode error'),
            (b'schema = [\n', 'TOML error'),
            (b'schema = 2\n', 'schema error'),
            (b'schema = 1\nkit = 42\n', 'configuration error'),
            (b'schema = 1\n[[rules]]\nname="x"\nkind="unknown"\nmessage="x"\n', 'rule validation error'),
            (b'schema = 1\n[[rules]]\nname="valid"\nkind="inject"\nmessage="{kit}/writing.md"\n'
             b'[[rules]]\nname="bad"\nkind="unknown"\n', 'rule validation error'),
        ]
        for data, reason in cases:
            with self.subTest(reason=reason):
                (self.root / 'rules.toml').write_bytes(data)
                found = self.findings()
                self.assertEqual(found['project rules']['status'], 'warning')
                self.assertIn(reason, found['project rules']['detail'])
                self.assertIn('kit directory unverified', found['project rules']['detail'])
                self.assertNotIn('rules kit directory', found)

    def test_read_and_directory_inspection_errors_do_not_claim_absence(self):
        self.write_rules('unavailable')
        with mock.patch.object(Path, 'read_text', side_effect=PermissionError('fixture read denied')):
            found = self.findings()
        self.assertIn('read error', found['project rules']['detail'])
        self.assertNotIn('rules kit directory', found)
        original = Path.stat

        def inaccessible(path, *args, **kwargs):
            if path == self.root / 'unavailable':
                raise PermissionError('fixture inspection denied')
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, 'stat', inaccessible):
            finding = self.findings()['rules kit directory']
        self.assertEqual(finding['status'], 'warning')
        self.assertIn('inspection unavailable (PermissionError)', finding['detail'])
        self.assertNotIn('does not exist', finding['detail'])

    def test_absent_rules_need_no_finding_and_non_file_is_a_read_error(self):
        self.assertEqual(self.findings(), {})
        (self.root / 'rules.toml').mkdir()
        finding = self.findings()['project rules']
        self.assertEqual(finding['status'], 'warning')
        self.assertIn('read error', finding['detail'])

    def test_cli_resolves_rules_from_project_root_and_preserves_warning_exit(self):
        identity = self.root.parent / 'gitconfig'
        identity.write_text('[user]\nname = min-seokkim\nemail = raptor210@snu.ac.kr\n', encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, env=child_env())
        (self.root / 'subfolder').mkdir()
        (self.root / 'custom-guides').mkdir()
        rules = self.write_rules('custom-guides')
        original = rules.read_bytes(), rules.stat().st_mtime_ns
        result = doctor(self.root / 'subfolder', identity)
        self.assertEqual(result.returncode, 0, result.stderr)
        findings = {row['item']: row for row in json.loads(result.stdout)}
        self.assertEqual(findings['rules kit directory']['status'], 'ok')
        self.assertIn(str(self.root / 'custom-guides'), findings['rules kit directory']['detail'])
        self.assertEqual((rules.read_bytes(), rules.stat().st_mtime_ns), original)
        self.assertFalse((self.root / '.awkit').exists())
        rules.write_text('schema = 2\n', encoding='utf-8')
        warning = doctor(self.root / 'subfolder', identity)
        self.assertEqual(warning.returncode, 0, warning.stderr)
        self.assertTrue(any(row['item'] == 'project rules' and row['status'] == 'warning'
                            for row in json.loads(warning.stdout)))

    def test_successive_valid_versions_cannot_mix_validation_and_consumption(self):
        first = ('schema=1\nkit="unused-first"\n[[rules]]\nname="first"\nkind="inject"\n'
                 'message="Literal note."\nprevents=["F29"]\n')
        changed_versions = [
            'schema=1\nrules=[]\n',
            ('schema=1\nkit="different-second"\n[[rules]]\nname="second"\nkind="block"\n'
             'message="Literal block."\nprevents=["F29"]\n'),
        ]
        for changed in changed_versions:
            with self.subTest(changed=changed):
                (self.root / 'rules.toml').write_text(first, encoding='utf-8')
                with mock.patch.object(Path, 'read_text', side_effect=[first, changed]) as reads:
                    found = self.findings()
                self.assertEqual(set(found), {'project rules'})
                self.assertEqual(found['project rules']['status'], 'ok')
                self.assertIn('1 valid rule', found['project rules']['detail'])
                self.assertEqual(reads.call_count, 1)  # One captured version supplies both validation and use.


if __name__ == "__main__":
    unittest.main()
