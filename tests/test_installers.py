"""Execute installers against isolated command stubs; never install a package."""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = shutil.which("sh")
if not SH and os.name == "nt":
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/sh.exe"
    SH = str(candidate) if candidate.is_file() else None
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(SH, "A POSIX shell is unavailable")
class PosixInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "app-python.txt"
        self.argv = self.root / "pipx-argv.txt"
        self.stub("uname", "printf 'Linux\\n'")
        self.stub("git", "exit 0")
        self.stub("pipx", '''case "$1" in
  install)
    printf '%s\\n' "$@" > "$INSTALLER_ARGV"
    target='pipx-default-3.11'
    while [ "$#" -gt 0 ]; do
      if [ "$1" = --python ]; then target="$2"; shift; fi
      shift
    done
    if [ ! -f "$INSTALLER_STATE" ]; then printf '%s\\n' "$target" > "$INSTALLER_STATE"; fi ;;
  environment) printf '%s\\n' "$INSTALLER_BIN" ;;
  ensurepath) : ;;
  *) exit 97 ;;
esac''')
        self.stub("awkit", '''if [ "$1" = doctor ]; then
  IFS= read -r actual < "$INSTALLER_STATE"
  printf 'actual-python=%s\\n' "$actual"
fi''')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def python(self, name, valid=True):
        executable = f"/fictional/Python with spaces/{name}"
        self.stub(name, f'''case "$*" in
  *sys.version_info*) exit {0 if valid else 1} ;;
  *sys.executable*) printf '%s\\n' {shlex.quote(executable)} ;;
  *) exit 96 ;;
esac''')
        return executable

    def run_installer(self):
        # Canonicalize PATH inside the shell so Git's MSYS shell also sees one directory.
        wrapper = self.root / "run.sh"
        wrapper.write_text('PATH="$(cd "$1" && pwd)"\nexport PATH\n. "$2"\n', encoding="utf-8", newline="\n")
        env = {**os.environ, "AWKIT_SOURCE": "fictional-source", "INSTALLER_ARGV": self.argv.as_posix(),
               "INSTALLER_STATE": self.state.as_posix(), "INSTALLER_BIN": self.bin.as_posix()}
        return subprocess.run([SH, str(wrapper), str(self.bin), str(ROOT / "install.sh")],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)

    def assert_new_interpreter(self, expected):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state.read_text(encoding="utf-8").strip(), expected)
        args = self.argv.read_text(encoding="utf-8").splitlines()
        self.assertEqual(args[args.index("--python") + 1], expected)  # spaces must remain one argument
        self.assertIn(f"actual-python={expected}", result.stdout)
        return result

    def test_standalone_python314_is_usable_without_other_python_names(self):
        self.assert_new_interpreter(self.python("python3.14"))

    def test_active_generic_python_wins_over_versioned_fallbacks(self):
        expected = self.python("python3")
        self.python("python3.14")
        self.assert_new_interpreter(expected)

    def test_invalid_generic_candidate_falls_back_to_314_before_older_python(self):
        self.python("python3", valid=False)
        expected = self.python("python3.14")
        self.python("python3.13")
        self.assert_new_interpreter(expected)

    def test_no_usable_candidate_exits_before_pipx_or_system_package_installation(self):
        self.python("python3", valid=False)
        self.python("python3.14", valid=False)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Missing: Python 3.11 or later", result.stdout)
        self.assertFalse(self.argv.exists())
        self.assertFalse(self.state.exists())

    def test_existing_pipx_default_cannot_override_fresh_environment_python(self):
        expected = self.python("python3.14")
        self.assert_new_interpreter(expected)
        self.assertNotEqual(expected, "pipx-default-3.11")

    def test_existing_application_keeps_its_python_without_reinstall_or_migration(self):
        selected = self.python("python3.14")
        self.state.write_text("existing-python-3.12\n", encoding="utf-8")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state.read_text(encoding="utf-8").strip(), "existing-python-3.12")
        self.assertIn("actual-python=existing-python-3.12", result.stdout)
        self.assertIn("existing pipx environments keep their Python", result.stdout)
        args = self.argv.read_text(encoding="utf-8").splitlines()
        self.assertEqual(args[args.index("--python") + 1], selected)
        self.assertEqual(args[0], "install")
        self.assertNotIn("reinstall", args)


@unittest.skipUnless(POWERSHELL, "PowerShell is unavailable")
class WindowsInstallerTests(unittest.TestCase):
    def run_fixture(self, available, existing=None):
        # Import only function definitions; the real installer entry point is never run unmocked.
        config = json.dumps({"available": available, "existing": existing, "source": str(ROOT / "install.ps1")})
        script = r'''$config = ConvertFrom-Json '__CONFIG__'
$tokens=$null; $errors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile($config.source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw $errors[0] }
$tree.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true) | ForEach-Object { Invoke-Expression $_.Extent.Text }
$script:trace = @()
$script:actual = $config.existing
$script:selected = $null
function Get-Command {
  param($Name, $ErrorAction)
  if ($Name -eq 'git') { return $true }
  if ($config.available.PSObject.Properties.Name -contains $Name) { return $true }
  return $null
}
function Update-SessionPath {}
function Install-WithWinget { throw 'Unexpected system package installation' }
function Invoke-FakePython {
  param($Name, [object[]]$Values)
  $global:LASTEXITCODE=0
  if ($Values -contains '-c') {
    if ($Values[-1] -like '*sys.version_info*') { Write-Output ([bool]$config.available.$Name); return }
    if ($Values[-1] -like '*sys.executable*') {
      $script:selected=$Name
      Write-Output "C:/fictional/Python with spaces/$Name.exe"
      return
    }
    throw 'Unexpected Python code'
  }
  $script:trace += ,@($Values)
  if ($Values -contains 'install') {
    $index=[array]::IndexOf($Values,'--python')
    if (-not $script:actual) { $script:actual = if ($index -ge 0) { $Values[$index+1] } else { 'pipx-default-3.11' } }
  }
  if ($Values -contains 'environment') { Write-Output ([IO.Path]::Combine([IO.Path]::GetTempPath(), 'nonexistent-awkit-installer-fixture-bin')) }
}
function python { Invoke-FakePython 'python' $args }
function python3 { Invoke-FakePython 'python3' $args }
function py { Invoke-FakePython 'py' $args }
function awkit { $global:LASTEXITCODE=0 }
$env:AWKIT_SOURCE='fictional-source'
Install-Awkit
Write-Output ('RESULT:' + ([PSCustomObject]@{selected=$script:selected;actual=$script:actual;calls=$script:trace} | ConvertTo-Json -Depth 6 -Compress))
'''.replace("__CONFIG__", config.replace("'", "''"))
        result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = next(line for line in result.stdout.splitlines() if line.startswith("RESULT:"))
        return json.loads(line.removeprefix("RESULT:")), result.stdout

    def test_path_python_wins_over_launcher_and_is_passed_to_fresh_pipx(self):
        data, _ = self.run_fixture({"python": True, "python3": True, "py": True})
        self.assertEqual(data["selected"], "python")
        self.assertEqual(data["actual"], "C:/fictional/Python with spaces/python.exe")

    def test_invalid_path_candidates_fall_back_to_usable_launcher(self):
        data, _ = self.run_fixture({"python": False, "python3": False, "py": True})
        self.assertEqual(data["selected"], "py")
        self.assertEqual(data["actual"], "C:/fictional/Python with spaces/py.exe")

    def test_python3_path_fallback_precedes_launcher(self):
        data, _ = self.run_fixture({"python": False, "python3": True, "py": True})
        self.assertEqual(data["selected"], "python3")

    def test_existing_app_interpreter_is_preserved_without_reinstall(self):
        data, output = self.run_fixture({"python": True, "py": True}, existing="existing-python-3.12")
        self.assertEqual(data["actual"], "existing-python-3.12")
        self.assertIn("existing pipx environments keep their Python", output)
        self.assertTrue(any("install" in call and "--python" in call for call in data["calls"]))
        self.assertFalse(any("reinstall" in call or "uninstall" in call for call in data["calls"]))
