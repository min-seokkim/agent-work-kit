"""Every module that builds a path under .awkit either prepares Git exclusion before writing (F7), or only reads.

A writer that forgets `local_state.prepare` puts awkit's state in front of `git add`. Writes take many forms
(SQLite files, copied run folders, JSON records), so instead of one wrapper this test finds the modules that name
`.awkit` and requires each to call `prepare` or to be listed here with the reason it writes nothing itself.
"""

import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "awkit"
# A `.awkit` path segment, not names such as `.awkit-artifacts` that live elsewhere.
MANAGED = re.compile(r"""["']\.awkit(?:/[^"']*)?["']""")
READS_ONLY = {
    "cli_channel.py": "passes the default channel path to Channel, which prepares it",
    "cli_kit.py": "names .awkit/ in messages and asks before removal; connect does the work",
    "local_state.py": "is where prepare is defined",
    "project_files.py": "defines the install-record paths that connect's Changes prepares before writing",
    "scan.py": "reports whether review folders exist",
}


class ManagedWrites(unittest.TestCase):
    def test_modules_naming_awkit_state_prepare_it_or_only_read(self):
        unprepared = []
        for path in sorted(SRC.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if MANAGED.search(text) and "prepare(" not in text and path.name not in READS_ONLY:
                unprepared.append(path.relative_to(SRC).as_posix())
        self.assertEqual(unprepared, [], "these modules name .awkit without preparing it; call local_state.prepare "
                                         "before writing, or add the module to READS_ONLY with the reason")

    def test_the_pattern_finds_managed_paths_only(self):
        for text in ('"/x" / ".awkit" / "done"', "Path('.awkit/channel.sqlite3')", '".awkit/"'):
            self.assertRegex(text, MANAGED)
        for text in ('".awkit-artifacts"', '".awkit-export"', "exclude.name + \".awkit-lock\""):
            self.assertNotRegex(text, MANAGED)

    def test_the_read_only_list_has_no_stale_entries(self):
        for name in READS_ONLY:
            text = (SRC / name).read_text(encoding="utf-8")
            self.assertRegex(text, MANAGED, f"{name} no longer names .awkit; remove it from READS_ONLY")


if __name__ == "__main__":
    unittest.main()
